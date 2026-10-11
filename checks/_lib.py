"""Thu vien dung chung cho cac trong tai (referee) cua pipeline.

Moi script checks/pN.py : kiem phase N bang BANG CHUNG THAT (build, HTTP that, SQLite that, fixture cuc bo)
roi exit 0 (PASS) / exit 1 (FAIL). Khong doc loi khai cua AI.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS: list[bool] = []


def header(phase: int, title: str) -> None:
    print("=" * 72)
    print(f"REFEREE PHASE {phase} — {title}")
    print(f"repo: {ROOT}")
    print("=" * 72)


def ok(msg: str) -> None:
    RESULTS.append(True)
    print(f"[OK]   {msg}")


def fail(msg: str) -> None:
    RESULTS.append(False)
    print(f"[FAIL] {msg}")


def note(msg: str) -> None:
    print(f"[..]   {msg}")


def check(cond: bool, good: str, bad: str) -> bool:
    """Gon: dung o dau cung duoc, tu ghi OK/FAIL."""
    if cond:
        ok(good)
    else:
        fail(bad)
    return bool(cond)


def finish() -> None:
    n = len(RESULTS)
    passed = sum(1 for r in RESULTS if r)
    verdict = "PASS" if (n and passed == n) else "FAIL"
    print("=" * 72)
    print(f"== ket qua phase: {verdict} ({passed}/{n}) ==")
    sys.exit(0 if verdict == "PASS" else 1)


# ---------------------------------------------------------------- file / ma nguon

def read(rel: str) -> str:
    p = ROOT / rel
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def pkg() -> dict:
    try:
        return json.loads(read("package.json") or "{}")
    except Exception:
        return {}


def src_text(patterns=("src/**/*.js", "src/**/*.jsx", "src/**/*.ts", "src/**/*.tsx",
                       "src/**/*.css", "index.html")) -> str:
    """Gop toan bo ma nguon frontend de tim nhan/chuoi (kiem tra tinh, khong phai chat luong)."""
    out = []
    for pat in patterns:
        for p in ROOT.glob(pat):
            if p.is_file():
                out.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(out)


def dist_text() -> str:
    out = []
    d = ROOT / "dist"
    if d.exists():
        for p in d.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".js", ".html", ".css", ".json"):
                out.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(out)


def major(ver: str) -> int:
    import re
    m = re.search(r"(\d+)", str(ver))
    return int(m.group(1)) if m else 0


# ---------------------------------------------------------------- chay lenh

def run(cmd: str, timeout: int = 900, cwd: Path | None = None) -> tuple[int, str]:
    """Chay lenh shell (Windows: dung cmd qua shell=True cua Python). Tra (exit_code, output)."""
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        p = subprocess.run(cmd, shell=True, cwd=str(cwd or ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT sau {timeout}s: {cmd}"
    except Exception as exc:                                   # pragma: no cover
        return 127, f"khong chay duoc: {type(exc).__name__}: {exc}"


def fresh_build(timeout: int = 900) -> tuple[int, str]:
    """XÓA dist/ rồi mới build.

    Vì sao: build lỗi thì dist CŨ vẫn nằm lại, nên cổng chỉ kiểm "có dist" sẽ bị qua mặt bằng
    artefact của lần build trước (đo thật 11/10: phá source -> build exit 1 nhưng dist cũ vẫn còn).
    Xóa trước khi build để chắc artefact là kết quả của SOURCE HIỆN TẠI — đúng yêu cầu
    "output build là kết quả của source vừa chỉnh sửa" trong safety gate của prompt.
    """
    import shutil
    d = ROOT / "dist"
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    return run("npm run build", timeout=timeout)


def tail(text: str, n: int = 800) -> str:
    text = (text or "").strip()
    return text[-n:] if len(text) > n else text


# ---------------------------------------------------------------- mang

def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def http_get(url: str, timeout: float = 8.0) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"").decode("utf-8", "replace")
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"


def wait_http(url: str, deadline_s: float = 45.0, expect: int = 200) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < deadline_s:
        code, _ = http_get(url, timeout=3.0)
        if code == expect:
            return True
        time.sleep(0.6)
    return False


class Proc:
    """Tien trinh nen (uvicorn, vite preview...) tu don dep khi thoat."""

    def __init__(self, cmd: str, cwd: Path | None = None):
        self.cmd = cmd
        self.p = subprocess.Popen(cmd, shell=True, cwd=str(cwd or ROOT),
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding="utf-8", errors="replace")

    def out(self) -> str:
        try:
            return self.p.stdout.read() if self.p.stdout else ""      # type: ignore[union-attr]
        except Exception:
            return ""

    def stop(self) -> None:
        try:
            self.p.terminate()
            self.p.wait(timeout=10)
        except Exception:
            try:
                self.p.kill()
            except Exception:
                pass


# ---------------------------------------------------------------- sqlite

def sqlite_tables(db: Path) -> list[str]:
    import sqlite3
    if not db.exists():
        return []
    with sqlite3.connect(str(db)) as c:
        rows = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return [r[0] for r in rows]


def sqlite_cols(db: Path, table: str) -> list[str]:
    import sqlite3
    if not db.exists():
        return []
    with sqlite3.connect(str(db)) as c:
        try:
            rows = c.execute(f"PRAGMA table_info({table})").fetchall()
        except Exception:
            return []
    return [r[1] for r in rows]


def find_db() -> Path | None:
    """Tim file SQLite cua backend (bo qua file trong node_modules/.venv)."""
    cands = []
    for pat in ("backend/**/*.db", "backend/**/*.sqlite", "backend/**/*.sqlite3", "*.db"):
        for p in ROOT.glob(pat):
            s = str(p).replace("\\", "/")
            if "node_modules" in s or ".venv" in s:
                continue
            cands.append(p)
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None
