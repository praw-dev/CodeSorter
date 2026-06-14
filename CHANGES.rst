############
 Change Log
############

codesorter follows `semantic versioning <https://semver.org/>`_.

************
 Unreleased
************

********************
 0.1.0 (2026/06/14)
********************

**Added**

- Initial release of CodeSorter.
- CLI interface with directory walking, sensible default excludes, ``.gitignore``
  honoring, and ``-e/--exclude`` / ``--no-default-excludes`` / ``--no-gitignore`` flags.
- Pre-commit hooks (``codesorter`` and ``codesorter-check``) for downstream consumers.
- Comprehensive test suite covering function, method, property, fixture, decorator, and
  inheritance sort behaviors.
- Example before/after files in ``examples/``.
