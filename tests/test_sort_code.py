"""Tests for the SortCodeCommand codemod."""

import libcst as cst
import pytest
from libcst.codemod import CodemodContext

from codesorter.sort_code import SortCodeCommand


class TestCLI:
    """Test cases for the CLI interface."""

    def test_cli_help(self, capsys):
        """Test that CLI help works."""
        from codesorter import main

        with pytest.raises(SystemExit) as exc_info:
            main(argv=["--help"])
        assert exc_info.value.code == 0
        assert "Sort Python code" in capsys.readouterr().out


class TestSortCodeCommand:
    """Test cases for SortCodeCommand."""

    def test_basic_function(self, test_files):
        """Test that functions are sorted correctly."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_class_global_dependency(self, test_files):
        """Test sorting with classes that depend on global variables."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_class_inheritance(self, test_files):
        """Test sorting with class inheritance."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_class_method(self, test_files):
        """Test that class methods are sorted correctly."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_classmethod(self, test_files):
        """Test that class methods are sorted correctly."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_codemod_does_not_break_syntax(self):
        """Test that the codemod doesn't break valid Python syntax."""
        code = """
def hello_world():
    return "Hello, World!"

class MyClass:
    def __init__(self):
        self.value = 42

    def get_value(self):
        return self.value
"""
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(code))

        # The result should still be valid Python
        try:
            compile(result.code, "<string>", "exec")
        except SyntaxError as e:
            pytest.fail(f"Codemod produced invalid Python syntax: {e}")

    def test_comprehensive(self, test_files):
        """Test comprehensive scenario with pytest fixtures, custom decorators, inheritance, and global dependencies."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_custom_decorators(self, test_files):
        """Test sorting with custom decorators."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_empty_module(self):
        """Test that empty modules are handled correctly."""
        code = ""
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(code))
        assert result.code.strip() == ""

    def test_mixed_decorators(self, test_files):
        """Test sorting with mixed decorators."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_module_with_only_imports(self):
        """Test that modules with only imports are handled correctly."""
        code = """
import os
import sys
from pathlib import Path
"""
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(code))
        # Should not change imports
        assert "import os" in result.code
        assert "import sys" in result.code
        assert "from pathlib import Path" in result.code

    def test_property(self, test_files):
        """Test that properties are sorted correctly."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_pytest_fixtures(self, test_files):
        """Test sorting with pytest fixtures."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_staticmethod(self, test_files):
        """Test that static methods are sorted correctly."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code
