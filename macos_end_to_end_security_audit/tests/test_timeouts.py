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


class FakeRunner:
    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    def run(self, cmd, timeout_s=0):
        self.calls += 1
        if self._results:
            return self._results.pop(0)
        # Default to timeout if exhausted.
        return self._default_timeout()

    def _default_timeout(self):
        return self.m.CommandResult(124, "(timeout)\n", kind="timeout", duration_ms=0)  # type: ignore[attr-defined]


class TestTimeouts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_audit_module()

    def test_btm_unknown_on_timeout(self):
        # Always timeout -> btm count should be unknown (-1), not 0.
        timeout_res = self.m.CommandResult(124, "(timeout)\n", kind="timeout", duration_ms=100)
        r = FakeRunner([timeout_res, timeout_res])
        r.m = self.m  # allow _default_timeout
        res = self.m.run_with_retry(r, ["sfltool", "dumpbtm"], [1, 2])
        self.assertEqual(res.kind, "timeout")
        self.assertEqual(self.m.btm_enabled_count_from_result(res, []), -1)

    def test_btm_retry_success(self):
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
"""
        timeout_res = self.m.CommandResult(124, "(timeout)\n", kind="timeout", duration_ms=100)
        ok_res = self.m.CommandResult(0, sample, kind="ok", duration_ms=120)
        r = FakeRunner([timeout_res, ok_res])
        r.m = self.m  # allow _default_timeout
        res = self.m.run_with_retry(r, ["sfltool", "dumpbtm"], [1, 2])
        self.assertEqual(res.kind, "ok")
        items = self.m.parse_sfltool_dumpbtm(res.out)
        self.assertEqual(self.m.btm_enabled_count_from_result(res, items), 1)


if __name__ == "__main__":
    unittest.main()

