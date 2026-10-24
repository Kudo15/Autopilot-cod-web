from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class BackupScriptContractTests(unittest.TestCase):
    def test_backup_script_copies_only_existing_database_and_never_deletes(self) -> None:
        text = (ROOT / "scripts" / "backup_db.ps1").read_text(encoding="utf-8")
        self.assertIn("Test-Path -LiteralPath $source", text)
        self.assertIn("Copy-Item -LiteralPath $source", text)
        self.assertNotIn("Remove-Item", text)

    def test_restore_preserves_original_and_rejects_same_target(self) -> None:
        text = (ROOT / "scripts" / "restore_db.ps1").read_text(encoding="utf-8")
        self.assertIn("Backup and target must be different", text)
        self.assertIn(".pre-restore-", text)
        self.assertIn("Copy-Item -LiteralPath $target -Destination $preserved", text)
        self.assertNotIn("Remove-Item", text)


if __name__ == "__main__":
    unittest.main()
