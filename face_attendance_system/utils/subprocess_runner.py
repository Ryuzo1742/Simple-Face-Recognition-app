"""Runs a worker script in a subprocess and parses its JSON stdout.

Both scripts/recognize_worker.py and scripts/train_worker.py print one
JSON object on success. If the worker crashes natively (segfault, DLL
load failure, etc.) or dies before printing anything, there's no JSON
to parse — this module turns that into a readable diagnosis instead of
a stack trace. The diagnosis is shown directly to the caller (not just
logged), because on some setups — especially a bundled .exe or an app
launched by double-click with no visible console — the person may have
no easy way to find logs/app.log on their own.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
WORKER_TIMEOUT_SECONDS = 180
STDERR_EXCERPT_CHARS = 600  # enough to see the real traceback without flooding the GUI

# Common crash exit codes, for a message a student can actually act on.
_SIGNAL_NAMES = {
    -11: "segmentation fault (SIGSEGV) — the native library crashed on bad memory access",
    -6: "aborted (SIGABRT) — a native library hit an internal assertion failure",
    -9: "killed (SIGKILL) — likely ran out of memory",
    3221225477: "Windows access violation — usually a broken/incompatible dlib install",
    -1073741819: "Windows access violation — usually a broken/incompatible dlib install",
}


class WorkerError(Exception):
    """Raised when a worker subprocess fails, with a diagnosis attached."""


def _stderr_excerpt(stderr: str) -> str:
    """The last part of stderr is almost always the actual traceback/error line."""
    text = (stderr or "").strip()
    if not text:
        return ""
    tail = text[-STDERR_EXCERPT_CHARS:]
    prefix = "..." if len(text) > STDERR_EXCERPT_CHARS else ""
    return f"\n\nDetails:\n{prefix}{tail}"


def run_worker(script_name: str, *args: str) -> dict[str, Any]:
    """Run scripts/<script_name> with args, return its parsed JSON result.

    Raises WorkerError with a human-readable message (including a
    stderr excerpt when available) on any failure — a clean error from
    the worker, a crash, empty output, or a timeout — so callers never
    need to distinguish "exception" from "process vanished".
    """
    script_path = SCRIPTS_DIR / script_name
    cmd = [sys.executable, "-u", str(script_path), *args]
    logger.info("Launching worker: %s", " ".join(cmd))

    # Force UTF-8 for the child's stdio. Without this, a redirected pipe on
    # Windows can fall back to the system codepage (e.g. cp1252); printing a
    # name or path with a character outside that codepage then raises
    # UnicodeEncodeError *inside the worker*, which can abort it before the
    # JSON line is ever written — producing exactly "empty output" with no
    # obvious cause. -u (above) disables stdio buffering for the same class
    # of "output never actually got flushed" failure.
    child_env = dict(os.environ)
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=WORKER_TIMEOUT_SECONDS,
            env=child_env,
        )
    except subprocess.TimeoutExpired:
        raise WorkerError(
            f"{script_name} did not finish within {WORKER_TIMEOUT_SECONDS}s and was treated "
            "as stuck. Try a smaller/clearer photo, or fewer students at once."
        )

    if result.stdout:
        logger.info("%s stdout:\n%s", script_name, result.stdout.strip())
    if result.stderr:
        logger.info("%s stderr:\n%s", script_name, result.stderr.strip())

    if result.returncode != 0:
        diagnosis = _SIGNAL_NAMES.get(result.returncode)
        if diagnosis:
            raise WorkerError(
                f"The recognition engine crashed ({diagnosis}). This is almost always a "
                f"broken dlib/face_recognition install.{_stderr_excerpt(result.stderr)}"
            )
        # A clean, non-crash failure — the worker may have printed its own {"error": ...}
        try:
            payload = json.loads(result.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            payload = None
        if payload and "error" in payload:
            raise WorkerError(payload["error"])
        raise WorkerError(
            f"The recognition engine exited unexpectedly (code {result.returncode})."
            f"{_stderr_excerpt(result.stderr)}"
        )

    stdout = (result.stdout or "").strip()
    if not stdout:
        # Exit code was 0 (no crash signal, no unhandled exception) but
        # nothing was printed — the only remaining explanation is that a
        # print itself failed (see the UTF-8 note above) or something
        # called sys.exit(0) early. Either way, stderr is the only lead.
        excerpt = _stderr_excerpt(result.stderr)
        base = "The recognition engine finished without returning a result, even though it reported success."
        if not excerpt:
            base += " No error output either — check logs/app.log for the full worker log."
        raise WorkerError(base + excerpt)

    try:
        # The worker may have logged extra lines; the JSON result is the last line.
        payload = json.loads(stdout.splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise WorkerError(
            f"Couldn't parse the recognition engine's output: {exc}{_stderr_excerpt(result.stderr)}"
        )

    if "error" in payload:
        raise WorkerError(payload["error"])

    return payload


def run_diagnostics() -> dict[str, Any]:
    """Run scripts/diagnostics_worker.py and return whatever it reported —
    even if it crashed partway through. Unlike run_worker(), this never
    raises: a diagnostic tool's whole job is to report exactly how far it
    got and where it stopped, crash included, not to fail loudly itself.
    """
    script_path = SCRIPTS_DIR / "diagnostics_worker.py"
    cmd = [sys.executable, "-u", str(script_path)]
    child_env = dict(os.environ)
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, env=child_env,
        )
    except subprocess.TimeoutExpired:
        return {"checks": [], "crashed": True, "crash_detail": "Diagnostics timed out after 60s."}

    checks: list[dict] = []
    # The worker prints its full cumulative state after every check, so
    # the LAST successfully printed line is the most complete picture —
    # even if a native crash cut it off mid-run.
    for line in (result.stdout or "").strip().splitlines():
        try:
            payload = json.loads(line)
            checks = payload.get("checks", checks)
        except json.JSONDecodeError:
            continue

    crashed = result.returncode != 0
    diagnosis = _SIGNAL_NAMES.get(result.returncode)
    return {
        "checks": checks,
        "crashed": crashed,
        "returncode": result.returncode,
        "crash_detail": diagnosis or _stderr_excerpt(result.stderr).strip(),
    }
