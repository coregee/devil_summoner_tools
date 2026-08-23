from __future__ import annotations

import contextlib
import io
import unittest

from psp import build


class PspBuildPipelineTests(unittest.TestCase):
    def test_default_profile_runs_every_configured_step_in_order(self) -> None:
        config = build.load_config()
        self.assertEqual(
            tuple(step.id for step in config.steps),
            (
                "repack_fonts",
                "repack_text",
                "repack_event_text",
                "build_fmv",
                "build_engine",
                "repack_visuals",
                "build_disc",
            ),
        )
        self.assertEqual(
            config.profiles["default"].steps,
            tuple(step.id for step in config.steps),
        )
        self.assertEqual(config.profiles["default"].outputs, ("game",))

    def test_plan_is_media_independent_and_lists_the_terminal_iso(self) -> None:
        config = build.load_config()
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            build.print_plan(
                config,
                config.profiles["default"],
                check=False,
            )
        output = stream.getvalue()
        self.assertIn("Mode: build", output)
        self.assertIn("font\\repack.py all", output)
        self.assertIn("text\\repack.py all", output)
        self.assertIn("text\\event_repack.py all", output)
        self.assertIn("fmv\\build.py all", output)
        self.assertIn("engine\\build.py all", output)
        self.assertIn("visual\\repack.py all", output)
        self.assertIn("rom\\repack.py game", output)
        self.assertIn("smtds_psp_in_progress.iso", output)

    def test_check_plan_selects_check_arguments_for_every_step(self) -> None:
        config = build.load_config()
        for step in config.steps:
            command = build._command(step, check=True)
            self.assertIsNotNone(command)
            assert command is not None
            self.assertEqual(command[-1], "--check")


if __name__ == "__main__":
    unittest.main()
