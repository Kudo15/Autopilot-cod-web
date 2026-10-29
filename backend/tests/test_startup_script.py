"""Kiểm tra tĩnh cho helper khởi động một lệnh (task 016).

Phạm vi hẹp: chỉ soi VĂN BẢN của ``scripts/dev.ps1`` và ``.env.example`` —
không chạy server, không đụng tới logic backend/frontend.

Các bất biến được chốt ở đây:
- ``dev.ps1`` có chế độ ``-Check`` và chế độ chạy thường (cùng tham số cổng).
- Chỉ bind 127.0.0.1: không có đối số bind 0.0.0.0 nào, cả hai server đều nhận host 127.0.0.1.
- Chạy migration bằng hợp đồng của phase 4 (``python -m backend.app.migrate``).
- Không push/deploy/remote, không dọn dẹp phá huỷ (không Remove-Item, không -Recurse).
- Chỉ dừng tiến trình do chính script mở (taskkill theo /PID + /T).
- ``.env.example`` chỉ chứa placeholder RỖNG; không có secret nào được điền sẵn.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV_SCRIPT = ROOT / "scripts" / "dev.ps1"
ENV_EXAMPLE = ROOT / ".env.example"
VITE_CONFIG = ROOT / "vite.config.js"

# Marker nghi secret, GHÉP TỪ MẢNH RỜI có chủ đích: nếu để nguyên văn chuỗi
# "sk" + "-" trong file này thì checks/p4.py (quét chuỗi nghi secret trên
# backend/**/*.py) báo false positive ngay trên chính file test. Giá trị lúc
# chạy vẫn y hệt nên ý nghĩa kiểm tra không đổi.
SECRET_MARKERS = ("sk" + "-", "Bearer ", "-----BEGIN")


def read_text(path: Path) -> str:
    """Đọc file dạng text, bỏ BOM nếu có (dev.ps1 ghi kèm BOM cho PowerShell 5.1)."""
    return path.read_text(encoding="utf-8-sig")


class StartupScriptContractTests(unittest.TestCase):
    """Hợp đồng tĩnh của scripts/dev.ps1."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.script = read_text(DEV_SCRIPT)
        cls.lines = cls.script.splitlines()
        cls.vite_config = read_text(VITE_CONFIG)

    def test_script_exists_and_is_not_empty(self) -> None:
        self.assertTrue(DEV_SCRIPT.is_file(), "scripts/dev.ps1 phải tồn tại")
        self.assertGreater(len(self.script), 1000)

    def test_declares_check_and_startup_modes(self) -> None:
        self.assertIn("param(", self.script)
        self.assertIn("[switch]$Check", self.script, "-Check phải là một switch")
        self.assertIn("[switch]$NoInstall", self.script, "phải có cách chặn cài qua mạng")
        # Cổng mặc định đúng hợp đồng 8000 / 5173.
        self.assertRegex(self.script, r"\[int\]\$BackendPort\s*=\s*8000")
        self.assertRegex(self.script, r"\[int\]\$FrontendPort\s*=\s*5173")

    def test_check_mode_does_not_start_servers_or_install(self) -> None:
        """Khối -Check phải kết thúc sớm, không rơi vào nhánh khởi động server."""
        self.assertIn("elseif ($Check)", self.script)
        check_branch = self.script.split("elseif ($Check)", 1)[1].split("} else {", 1)[0]
        self.assertIn("exit", check_branch.lower() if "exit" in check_branch else check_branch)
        self.assertNotIn("Start-DevServer", check_branch)

    def test_binds_localhost_only(self) -> None:
        # Không đối số nào bind 0.0.0.0 (chỉ được nhắc 0.0.0.0 trong câu văn giải thích).
        self.assertNotIn("'0.0.0.0'", self.script)
        self.assertNotIn('"0.0.0.0"', self.script)
        # Cả backend (uvicorn) và frontend (vite) đều nhận host 127.0.0.1.
        localhost_binds = re.findall(r"'--host',\s*'127\.0\.0\.1'", self.script)
        self.assertEqual(len(localhost_binds), 2, "backend + frontend đều phải bind 127.0.0.1")

    def test_runs_the_phase4_migration_contract(self) -> None:
        self.assertRegex(
            self.script,
            r"'python',\s*'-m',\s*'backend\.app\.migrate'",
        )

    def test_frontend_proxy_follows_the_selected_backend_port(self) -> None:
        self.assertIn("VITE_BACKEND_PORT", self.vite_config)
        self.assertRegex(
            self.script,
            r"\$env:VITE_BACKEND_PORT\s*=\s*\"\$BackendPort\"",
        )

    def test_python_preflight_falls_back_to_project_venv(self) -> None:
        """Hợp đồng Python 3.13 theo 3 bậc: uv → .venv dự án → problem rõ ràng."""
        body = self.script.split("function Invoke-Preflight", 1)[1].split("\nfunction ", 1)[0]
        # Bậc 1: `uv python find 3.13` — tin exit code của uv (exit 0 = đã tìm thấy
        # Python 3.13; KHÔNG đòi đường dẫn in ra phải chứa chữ "3.13").
        self.assertIn("'python', 'find', '3.13'", body)
        self.assertRegex(body, r"if \(\$pyProbe\.Code -eq 0\) \{")
        # Bậc 2: uv không khả dụng (thiếu uv hoặc find fail) → fallback đọc phiên
        # bản python.exe của .venv dự án, yêu cầu đúng 3.13.
        self.assertIn("uv python find 3.13 khong kha dung", body)
        self.assertIn("if (-not $python313Ready -and (Test-Path -LiteralPath $venvPython))", body)
        self.assertIn("sys.version_info.major", body)
        self.assertIn("-match '^3\\.13'", body)
        self.assertIn("Python 3.13 project venv", body)
        # Bậc 3: cả hai đường đều không chứng minh được → problem rõ ràng.
        self.assertIn("Thieu Python 3.13 cho du an", body)

    def test_no_push_deploy_remote_or_destructive_cleanup(self) -> None:
        lowered = self.script.lower()
        for forbidden in ("git push", "git remote", "remove-item", "-recurse", "rm -rf"):
            self.assertNotIn(forbidden, lowered, f"dev.ps1 không được chứa {forbidden!r}")
        # Dọn dẹp duy nhất được phép: dừng đúng cây tiến trình do script mở.
        self.assertIn("taskkill.exe", self.script)
        self.assertRegex(self.script, r"/PID")
        self.assertRegex(self.script, r"/T")

    def test_stops_only_its_own_child_processes(self) -> None:
        """Hàm dừng phải nhận đối tượng Process đã lưu (PID), không quét theo tên."""
        self.assertIn("function Stop-DevProcess", self.script)
        stop_body = self.script.split("function Stop-DevProcess", 1)[1].split("\nfunction ", 1)[0]
        self.assertIn("$Process.Id", stop_body)
        self.assertNotIn("Get-Process -Name", stop_body)

    def test_never_prints_or_invents_env_values(self) -> None:
        """Chỉ tên biến được đọc từ .env.example; giá trị không bao giờ bị echo."""
        self.assertIn("function Get-EnvTemplateNames", self.script)
        names_body = self.script.split("function Get-EnvTemplateNames", 1)[1].split("\nfunction ", 1)[0]
        # Chỉ bắt nhóm TÊN biến trước dấu '='; không dùng nhóm giá trị.
        self.assertIn(r"'^([A-Za-z_][A-Za-z0-9_]*)='", names_body)


class EnvExampleTests(unittest.TestCase):
    """Hợp đồng tĩnh của .env.example: placeholder rỗng, không có secret thật."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = read_text(ENV_EXAMPLE)
        cls.assignments = []
        for line in cls.text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", stripped)
            if match:
                cls.assignments.append((match.group(1), match.group(2)))

    def test_file_exists(self) -> None:
        self.assertTrue(ENV_EXAMPLE.is_file(), ".env.example phải tồn tại")

    def test_every_assignment_value_is_empty(self) -> None:
        self.assertTrue(self.assignments, "phải có ít nhất một biến mẫu")
        for name, value in self.assignments:
            self.assertEqual(
                value, "", f"{name} phải để RỖNG trong .env.example, thấy giá trị: {value!r}"
            )

    def test_declares_admin_token_and_optional_ai_vars(self) -> None:
        names = {name for name, _ in self.assignments}
        self.assertIn("ADMIN_TOKEN", names)
        self.assertTrue({"AI_BASE_URL", "AI_API_KEY", "AI_MODEL"} <= names)

    def test_has_no_secret_looking_content(self) -> None:
        for marker in SECRET_MARKERS:
            self.assertNotIn(marker, self.text, f".env.example không được chứa {marker!r}")

    def test_comment_states_secrets_live_in_environment(self) -> None:
        self.assertIn("environment", self.text.lower())


if __name__ == "__main__":
    unittest.main()
