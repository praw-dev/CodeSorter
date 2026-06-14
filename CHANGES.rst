############
 Change Log
############

codesorter follows `semantic versioning <https://semver.org/>`_.

************
 Unreleased
************

**Added**

- Sort keyword arguments in calls, keyword-only parameters in function definitions, and
  string keys in dict literals alphabetically. In a call, keyword arguments are sorted
  and ``**`` unpackings moved to the end (positional arguments and ``*`` unpackings stay
  put), which is safe because a call raises ``TypeError`` on any duplicate keyword
  regardless of order. In a dict literal, ``**`` spreads and non-string keys act as
  barriers so last-wins merge semantics are preserved.

**Changed**

- Sort ``_``-prefixed (private and dunder) names ahead of public names at every level
  rather than after capitalized names. A plain string sort placed ``_`` after
  ``A``-``Z`` because of its higher code point; names are now ordered on a
  leading-underscore flag first so private definitions, methods, keyword arguments, and
  dict keys group together ahead of the public ones.

**Fixed**

- Order definitions with a proper priority topological sort so a class or function is
  always placed after every sibling it depends on. The previous dependency heuristic
  compared per-node dependency vectors and could emit a dependent before its dependency
  (for example, ``Subreddit``'s ``SubredditFlair`` was sorted ahead of the
  flair-template classes it instantiates).

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
