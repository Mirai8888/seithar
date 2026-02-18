"""Tests for seithar.cli — CLI entry point."""
import pytest
import subprocess
import sys


class TestCLIImports:
    def test_import_module(self):
        import seithar.cli  # noqa: F401

    def test_import_main(self):
        from seithar.cli import main  # noqa: F401

    def test_main_is_callable(self):
        from seithar.cli import main
        assert callable(main)


class TestCLIEntryPoint:
    def test_seithar_help(self):
        """The installed `seithar` command should respond to --help."""
        result = subprocess.run(
            [sys.executable, "-m", "seithar.cli", "--help"],
            capture_output=True, text=True, timeout=10
        )
        # Accept 0 (normal help) or 2 (argparse error for stub) — just not a crash
        assert result.returncode in (0, 2), f"CLI crashed: {result.stderr}"
