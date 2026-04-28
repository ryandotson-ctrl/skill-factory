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


class TestPDFSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_audit_module()

    def test_pdf_bytes(self):
        b = self.m.PDFBuilder()
        l = self.m.PDFLayout(b, report_title="T", generated="now")
        l.heading("Hello", level=1)
        l.paragraph("World")
        l.finish()
        pdf = b.build()
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"/Type /Page", pdf)


if __name__ == "__main__":
    unittest.main()
