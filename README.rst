############
 CodeSorter
############

CodeSorter is a LibCST codemod that automatically sorts and organizes Python code.

**********
 Features
**********

- **Smart Sorting**: Automatically sorts functions, classes, and methods alphabetically
- **Decorator Awareness**: Properly handles ``@property``, ``@staticmethod``,
  ``@classmethod``, and ``@pytest.fixture`` decorators
- **Hierarchical Organization**: Maintains logical grouping within classes and modules
- **Pytest Integration**: Special handling for pytest fixtures with proper scope
  ordering
- **CLI Interface**: Simple command-line interface for easy integration
- **Pre-commit Hook**: Ready-to-use pre-commit hook for automated code organization

**************
 Installation
**************

From PyPI:

.. code-block:: bash

    # using uv and add to the lint dependency group
    uv add --group lint codesorter
    # or using pip
    pip install codesorter

From Source:

.. code-block:: bash

    git clone https://github.com/LilSpazJoekp/codesorter.git
    cd codesorter
    uv pip install -e .

Development Installation:

.. code-block:: bash

    git clone https://github.com/LilSpazJoekp/codesorter.git
    cd codesorter
    uv sync

*******
 Usage
*******

Command Line Interface
======================

The simplest way to use CodeSorter is through the command-line interface:

.. code-block:: bash

    # Sort a single file
    codesorter my_file.py

    # Sort all Python files in a directory
    codesorter my_project/

    # Sort with additional options
    codesorter --help

Pre-commit Hook
===============

Add CodeSorter to your pre-commit configuration to automatically sort code on every
commit:

.. code-block:: yaml

    # .pre-commit-config.yaml
    repos:
      - repo: https://github.com/LilSpazJoekp/codesorter
        rev: v0.0.3
        hooks:
          - id: codesorter

Or use the check-only variant, which fails the hook without modifying files:

.. code-block:: yaml

    repos:
      - repo: https://github.com/LilSpazJoekp/codesorter
        rev: v0.0.3
        hooks:
          - id: codesorter-check

Programmatic Usage
==================

You can also use CodeSorter programmatically:

.. code-block:: python

    import libcst as cst
    from codesorter.sort_code import SortCodeCommand
    from libcst.codemod import CodemodContext

    # Parse your code
    code = """
    def z_function():
        pass

    def a_function():
        pass
    """

    # Create context and command
    context = CodemodContext()
    command = SortCodeCommand(context)

    # Transform the code
    result = command.transform_module(cst.parse_module(code))
    print(result.code)

**************
 How It Works
**************

CodeSorter uses LibCST (Concrete Syntax Tree) to parse and transform Python code. It
applies sophisticated sorting rules:

Function Sorting
================

- Functions are sorted alphabetically by name
- Global functions are sorted separately from class methods

Class Method Sorting
====================

- Methods are sorted with special consideration for decorators: - ``@property`` methods
  (getters, setters, deleters) - ``@staticmethod`` methods - ``@classmethod`` methods -
  Regular instance methods
- Methods within classes maintain their logical grouping

Pytest Fixture Sorting
======================

- Fixtures are sorted by scope (session, package, module, class, function)
- Within each scope, fixtures are sorted alphabetically
- ``autouse`` fixtures are handled specially

Example Transformation
======================

**Before:**

.. code-block:: python

    class MyClass:
        def z_method(self):
            pass

        @property
        def a_property(self):
            pass

        @staticmethod
        def b_static():
            pass

**After:**

.. code-block:: python

    class MyClass:
        @property
        def a_property(self):
            pass

        @staticmethod
        def b_static():
            pass

        def z_method(self):
            pass

*************
 Development
*************

Setting Up Development Environment
==================================

.. code-block:: bash

    # Clone the repository
    git clone https://github.com/LilSpazJoekp/codesorter.git
    cd codesorter

    # Install with development dependencies
    uv sync

    # Install pre-commit hooks
    uv run pre-commit install

Running Tests
=============

.. code-block:: bash

    # Run all tests
    uv run pytest

    # Run a specific test file
    uv run pytest tests/test_sort_code.py

    # Run the full tox matrix (tests, type, pre-commit)
    uv run tox

Code Quality
============

The project uses several tools to maintain code quality:

- **Ruff**: Fast linting and formatting
- **Pyright**: Type checking
- **Pre-commit**: Automated quality checks

Run all quality checks:

.. code-block:: bash

    uv run pre-commit run --all-files

**************
 Contributing
**************

1. Fork the repository
2. Create a feature branch: ``git checkout -b feature-name``
3. Make your changes and add tests
4. Run the test suite: ``uv run pytest``
5. Run pre-commit hooks: ``pre-commit run --all-files``
6. Commit your changes: ``git commit -m "Add feature"``
7. Push to your fork: ``git push origin feature-name``
8. Create a Pull Request

**********
 Examples
**********

See the ``examples/`` directory for before and after examples of CodeSorter in action:

- ``examples/before_example.py``: Unsorted code
- ``examples/after_example.py``: Same code after sorting

*********
 License
*********

This project is licensed under the MIT License - see the `LICENSE.txt
<https://github.com/LilSpazJoekp/codesorter/blob/main/LICENSE.txt>`_ file for details.

***********
 Changelog
***********

See the `change log
<https://codesorter.readthedocs.io/en/latest/package_info/change_log.html>`_ for the
full list of changes.
