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


class TestParsers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_audit_module()

    def test_parse_launchctl_print(self):
        sample = """gui/501/com.example.service = {
\tstate = not running
\truns = 12
\tlast exit code = 78: EX_CONFIG
}\n"""
        st = self.m.parse_launchctl_print(sample)
        self.assertIn("gui/501/", st.label)
        self.assertEqual(st.state, "not running")
        self.assertEqual(st.runs, 12)
        self.assertIn("EX_CONFIG", st.last_exit)

    def test_parse_lsof_listen(self):
        sample = """COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME
ControlCe 596 user 10u IPv4 0x0 0t0 TCP *:7000 (LISTEN)
rapportd  603 user 13u IPv4 0x0 0t0 TCP *:49152 (LISTEN)
"""
        ls = self.m.parse_lsof_listen(sample)
        self.assertEqual(len(ls), 2)
        self.assertEqual(ls[0].process, "ControlCe")
        self.assertIn(":7000", ls[0].listen)

    def test_parse_sfltool_dumpbtm_enabled(self):
        sample = """========================
 Records for UID 501 : AAAA
========================

 Items:

 #1:
                 Name: node
          Disposition: [enabled, allowed, notified] (0xb)
           Identifier: 8.com.example.gateway
      Executable Path: /opt/homebrew/bin/node
      Team Identifier: (null)

 #2:
                 Name: Something
          Disposition: [disabled, allowed, not notified] (0x2)
           Identifier: 8.com.disabled
      Executable Path: /tmp/disabled
"""
        items = self.m.parse_sfltool_dumpbtm(sample)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].identifier, "8.com.example.gateway")
        self.assertEqual(items[0].exec_path, "/opt/homebrew/bin/node")

    def test_normalize_assess_target(self):
        self.assertEqual(
            self.m.normalize_assess_target("/Applications/Foo.app/Contents/MacOS/Foo"),
            "/Applications/Foo.app",
        )
        self.assertEqual(
            self.m.normalize_assess_target("/Library/Bar.appex/Contents/MacOS/Bar"),
            "/Library/Bar.appex",
        )
        self.assertEqual(
            self.m.normalize_assess_target("/opt/homebrew/bin/python3"),
            "/opt/homebrew/bin/python3",
        )

    def test_classify_spctl_summary(self):
        self.assertEqual(
            self.m.classify_spctl_summary("Foo.app: accepted source=Notarized Developer ID"),
            "accepted_notarized",
        )
        self.assertEqual(
            self.m.classify_spctl_summary("Foo.app: accepted source=Developer ID"),
            "accepted_dev_id",
        )
        self.assertEqual(
            self.m.classify_spctl_summary("rejected (the code is valid but does not seem to be an app)"),
            "rejected_not_app",
        )
        self.assertEqual(
            self.m.classify_spctl_summary("rejected (code has no resources but signature indicates they must be present)"),
            "rejected_resources_missing",
        )
        self.assertEqual(
            self.m.classify_spctl_summary("Foo: rejected"),
            "rejected_other",
        )


if __name__ == "__main__":
    unittest.main()
