import importlib.util
from pathlib import Path
import sys
import unittest


def load_audit_module():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "audit_and_report.py"
    spec = importlib.util.spec_from_file_location("audit_and_report", script)
    mod = importlib.util.module_from_spec(spec)
    # Python 3.14 dataclasses may consult sys.modules during decoration.
    sys.modules[spec.name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_audit_module()

    def test_defaults_console_only(self):
        cfg = self.m.parse_args([])
        self.assertFalse(cfg.generate_pdf)
        self.assertIsNone(cfg.output_pdf)
        self.assertFalse(cfg.keep_history)
        self.assertEqual(cfg.format, "text")
        self.assertFalse(cfg.diff_last)
        self.assertEqual(cfg.recent_apps_days, 14)
        self.assertEqual(cfg.recent_apps_max, 20)
        self.assertIsNone(cfg.tcc_recent_log_minutes)

        expected = Path.home() / "Library/Application Support/macos_end_to_end_security_audit/reports"
        self.assertEqual(cfg.output_dir, expected)

    def test_pdf_flag(self):
        cfg = self.m.parse_args(["--pdf"])
        self.assertTrue(cfg.generate_pdf)

    def test_output_pdf_implies_pdf(self):
        cfg = self.m.parse_args(["--output-pdf", "/tmp/security_audit_report.pdf"])
        self.assertTrue(cfg.generate_pdf)
        self.assertIsNotNone(cfg.output_pdf)
        self.assertEqual(str(cfg.output_pdf), "/tmp/security_audit_report.pdf")

    def test_deep_defaults_recent_apps(self):
        cfg = self.m.parse_args(["--depth", "deep"])
        self.assertEqual(cfg.recent_apps_days, 60)
        self.assertEqual(cfg.recent_apps_max, 60)

    def test_format_json_flag(self):
        cfg = self.m.parse_args(["--format", "json"])
        self.assertEqual(cfg.format, "json")


if __name__ == "__main__":
    unittest.main()
