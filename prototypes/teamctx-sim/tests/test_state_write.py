import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fakes  # noqa: F401  (puts prototypes/teamctx-sim on sys.path)
from simlib import state


class AtomicWriteTests(unittest.TestCase):
    def test_retries_when_windows_briefly_denies_the_swap(self):
        # Regression: the live view reading map.json made os.replace fail once and the run crashed.
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "map.json"
            path.write_text("old", encoding="utf-8")
            real = os.replace
            calls = {"n": 0}

            def flaky(src, dst):
                calls["n"] += 1
                if calls["n"] <= 2:
                    raise PermissionError(5, "Access is denied")
                return real(src, dst)

            with mock.patch.object(state.os, "replace", side_effect=flaky), \
                    mock.patch.object(state.time, "sleep"):
                state.atomic_write_text(path, "new")
            self.assertEqual(path.read_text(encoding="utf-8"), "new")
            self.assertEqual(calls["n"], 3)

    def test_gives_up_after_persistent_denial(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "map.json"
            with mock.patch.object(state.os, "replace", side_effect=PermissionError(5, "denied")), \
                    mock.patch.object(state.time, "sleep"):
                with self.assertRaises(PermissionError):
                    state.atomic_write_text(path, "new")


if __name__ == "__main__":
    unittest.main()
