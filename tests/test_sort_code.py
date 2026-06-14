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

    def test_alias_function(self, test_files):
        """Test that an assignment aliasing a method is kept after that method.

        ``alias = method`` is an assignment, which by category sorts ahead of methods,
        but it depends on the method it references, so the topological sort must keep it
        after its target rather than letting it float to the top (which would raise a
        ``NameError`` at class-definition time).

        """
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_augmented_assignment(self, test_files):
        """Test that an augmented assignment stays adjacent to the constant it augments."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_barrier(self, test_files):
        """Test that definitions are not reordered across a side-effecting statement.

        A bare statement such as ``sys.path.insert(0, str(REPO_ROOT))`` is a barrier:
        the constants before it (which it may use) must stay before it, so sorting
        happens only within each segment between barriers rather than across the whole
        module.

        """
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

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

    def test_comprehension_dependency(self, test_files):
        """Test that a name used in a module-level comprehension is a real dependency.

        A module-level comprehension runs eagerly when the module executes, so an
        assignment built from one must follow the function it calls (the reference lives
        in a comprehension scope, which previously hid the dependency). A comprehension
        inside a function body stays deferred and imposes no ordering.

        """
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_comprehensive(self, test_files):
        """Test comprehensive scenario with pytest fixtures, custom decorators, inheritance, and global dependencies."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_constant_ordering(self, test_files):
        """Test that constants sort before classes and methods, respecting dependencies."""
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

    def test_keyword_arguments(self, test_files):
        """Test that keyword arguments, keyword-only params, and dict keys are sorted."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_lazy_annotation_cycle(self, test_files):
        """Test that a forward reference in a lazy annotation does not force a cycle.

        Under ``from __future__ import annotations`` an annotation is a lazy string, so
        ``class Apple`` annotated with ``Instr`` must not be treated as depending on the
        ``Instr = Apple | Zebra`` alias. The value-level union genuinely depends on
        ``Apple``/``Zebra`` and must follow them; the lazy-annotation edge is dropped so
        no false cycle hoists ``Instr`` above its members (which would raise NameError).

        """
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

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

    def test_name_rebinding(self, test_files):
        """Test that an assignment rebinding a method name stays after that method.

        ``ten = cachedproperty(ten, ...)`` binds the same name as the ``def ten`` above
        it and wraps that method, so the assignment must keep its position after the
        method (moving it ahead would raise ``NameError`` and change which binding
        wins). Property getter/setter/deleter groups are unaffected — they carry no
        assignment.

        """
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_order_sensitive(self, test_files):
        """Test that enum, dataclass, and named-tuple member order is preserved."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

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

    def test_underscore_ordering(self, test_files):
        """Test that ``_``-prefixed names sort ahead of public names at every level."""
        input_code, expected_code = test_files
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(input_code))

        assert expected_code == result.code

    def test_whitespace_not_introduced(self):
        """Test that reordering keeps blank lines with their slot, not the moved node.

        The blank line after the docstring must stay at the top of the block rather than
        travelling down with ``STR_FIELD``, and the comment must stay attached to the
        attribute it documents.

        """
        code = '''class Subreddit:
    """A subreddit."""

    STR_FIELD = "display_name"
    MAX_CAPTION_LENGTH = 180
    MESSAGE_PREFIX = "#"

    # Bound at import time to avoid circular imports.
    _submission_class: int

    def method(self):
        return None
'''
        expected = '''class Subreddit:
    """A subreddit."""

    MAX_CAPTION_LENGTH = 180
    MESSAGE_PREFIX = "#"
    STR_FIELD = "display_name"

    # Bound at import time to avoid circular imports.
    _submission_class: int

    def method(self):
        return None
'''
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(code))

        assert expected == result.code

    def test_whitespace_trailer_stays_tight(self):
        """Test that an anchored augmented assignment stays tight to its constant.

        The ``__all__ += ...`` trailer must stay directly under ``__all__ = [...]`` with
        no blank line between them, and the blank-line separator must land before the
        ``__version__`` assignment that sorts after it.

        """
        code = """__version__ = "1.0"

__all__ = [
    "Beta",
    "Alpha",
]
__all__ += extra.__all__
"""
        expected = """__all__ = [
    "Beta",
    "Alpha",
]
__all__ += extra.__all__

__version__ = "1.0"
"""
        context = CodemodContext()
        command = SortCodeCommand(context)
        result = command.transform_module(cst.parse_module(code))

        assert expected == result.code
