"""Background jobs for long odoo-bin runs: logs on disk, process-group kill, per-database lock."""
from __future__ import annotations

import os
import re
import signal
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..util import ToolError

_TS = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+ \d+ (\w+) ")
_SUMMARY = re.compile(r"(\d+) failed, (\d+) error\(s\) of (\d+) tests")
_SKIPPED = re.compile(r"skipped (\S+) : (.*)$|SkipTest[:(]\s*(.*)$", re.M)
_FAILURE_START = re.compile(r"(FAIL|ERROR): (\w+\.\w+)|^(FAIL|ERROR): ")
_CRITICAL = re.compile(r" (CRITICAL|ERROR) \S+ (odoo\.modules\.loading|odoo\.modules\.registry|odoo\.tools\.convert|"
                       r"odoo\.addons\.base\.models\.ir_ui_view|odoo\.sql_db)")


@dataclass
class Job:
    id: str
    kind: str
    title: str
    db: str | None
    cmd: list[str]
    log_path: Path
    started: float = field(default_factory=time.time)
    finished: float | None = None
    status: str = "running"  # running, passed, failed, error, cancelled, timeout, stopped
    returncode: int | None = None
    proc: subprocess.Popen | None = None
    summary: dict = field(default_factory=dict)
    note: str = ""

    def elapsed(self) -> float:
        return round((self.finished or time.time()) - self.started, 1)


def parse_log(text: str, max_blocks: int = 8) -> dict:
    """Extract test totals, failure/error blocks and fatal loading errors from an Odoo log."""
    totals = [tuple(map(int, m)) for m in _SUMMARY.findall(text)]
    failed = sum(t[0] for t in totals)
    errors = sum(t[1] for t in totals)
    tests = sum(t[2] for t in totals)
    lines = text.splitlines()
    blocks: list[str] = []
    i = 0
    while i < len(lines) and len(blocks) < max_blocks:
        line = lines[i]
        level = _TS.match(line)
        is_fail = level and level.group(1) in {"ERROR", "CRITICAL"} and (
            _FAILURE_START.search(line) or _CRITICAL.search(line) or "Traceback" in line
            or "ParseError" in line or "Failed to load" in line)
        if is_fail:
            block = [line]
            j = i + 1
            while j < len(lines) and not _TS.match(lines[j]) and len(block) < 60:
                block.append(lines[j])
                j += 1
            blocks.append("\n".join(block))
            i = j
            continue
        i += 1
    skipped = [(m.group(1) or "test", (m.group(2) or m.group(3) or "").strip()[:200]) for m in _SKIPPED.finditer(text)]
    return {"tests": tests, "failed": failed, "errors": errors, "error_blocks": blocks, "skipped": skipped,
            "loading_failed": bool(re.search(r"Failed to load registry|ParseError|Invalid view definition|"
                                             r"odoo\.modules\.loading: .*(?:error|failed)", text, re.I))}


class JobManager:
    def __init__(self, jobs_dir: Path):
        self.dir = jobs_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, Job] = {}
        self.db_locks: dict[str, str] = {}
        self.lock = threading.Lock()

    def start(self, kind: str, title: str, cmd: list[str], db: str | None = None, timeout: int | None = 1800,
              cwd: str | None = None, env: dict | None = None,
              on_finish: Callable[[Job, str], None] | None = None) -> Job:
        with self.lock:
            if db and db in self.db_locks and self.jobs[self.db_locks[db]].status == "running":
                raise ToolError(f"job {self.db_locks[db]} is already using database {db!r}; wait or cancel it")
            job_id = time.strftime("%H%M%S-") + uuid.uuid4().hex[:6]
            log_path = self.dir / f"{job_id}-{kind}.log"
            job = Job(job_id, kind, title, db, cmd, log_path)
            self.jobs[job_id] = job
            if db:
                self.db_locks[db] = job_id
        log = open(log_path, "w", buffering=1, encoding="utf-8", errors="replace")  # noqa: SIM115
        log.write(f"$ {' '.join(cmd)}\n")
        job.proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=cwd, start_new_session=True,
                                    env={**os.environ, **(env or {})})
        threading.Thread(target=self._wait, args=(job, log, timeout, on_finish), daemon=True,
                         name=f"job-{job_id}").start()
        return job

    def _wait(self, job: Job, log, timeout: int | None, on_finish) -> None:
        try:
            job.returncode = job.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._kill(job)
            job.status = "timeout"
            job.returncode = job.proc.wait()
        finally:
            log.close()
        text = job.log_path.read_text(encoding="utf-8", errors="replace")
        job.summary = parse_log(text)
        if job.status == "running":
            if job.kind == "server":
                job.status = "stopped"
            elif job.returncode != 0 or job.summary["loading_failed"]:
                job.status = "failed" if job.summary["failed"] or job.summary["errors"] else "error"
            elif job.summary["failed"] or job.summary["errors"]:
                job.status = "failed"
            else:
                job.status = "passed"
        job.finished = time.time()
        if on_finish:
            try:
                on_finish(job, text)
            except Exception as exc:  # noqa: BLE001
                job.note += f" cleanup failed: {exc}"
        with self.lock:
            if job.db and self.db_locks.get(job.db) == job.id:
                del self.db_locks[job.db]

    @staticmethod
    def _kill(job: Job) -> None:
        if job.proc and job.proc.poll() is None:
            try:
                os.killpg(job.proc.pid, signal.SIGTERM)
                time.sleep(3)
                if job.proc.poll() is None:
                    os.killpg(job.proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        if job.status == "running":
            job.status = "cancelled" if job.kind != "server" else "stopped"
            self._kill(job)
        return job

    def get(self, job_id: str) -> Job:
        if job_id not in self.jobs:
            known = ", ".join(list(self.jobs)[-10:]) or "none"
            raise ToolError(f"unknown job {job_id!r} (jobs of this session: {known})")
        return self.jobs[job_id]

    def tail(self, job_id: str, lines: int = 80, grep: str | None = None) -> str:
        job = self.get(job_id)
        text = job.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if grep:
            rx = re.compile(grep, re.I)
            text = [line for line in text if rx.search(line)]
        return "\n".join(text[-lines:])
