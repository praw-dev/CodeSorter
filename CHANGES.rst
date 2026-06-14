############
 Change Log
############

codesorter follows `semantic versioning <https://semver.org/>`_.

************
 Unreleased
************

**Changed**

- Format reordered files with ``ruff`` by default instead of ``black``, so a downstream
  project no longer needs a ``.libcst.codemod.yaml`` to use the ``codesorter`` CLI or
  pre-commit hook. ``ruff`` must be importable on the ``PATH`` when sorting.

**Fixed**

- Keep an assignment that rebinds a name also bound by a sibling in its original
  position relative to that sibling. For example ``ten = cachedproperty(ten, ...)``
  following ``def ten`` now stays after the method it wraps instead of being hoisted
  ahead of it (which raised ``NameError`` and changed which binding wins). Property
  getter/setter/deleter groups, which carry no assignment, are still ordered by their
  sort key.

********************
 0.2.1 (2026/06/14)
********************

**Fixed**

- Treat a name used inside a module- or class-level comprehension as a real dependency.
  Such a comprehension runs eagerly when the definition executes, so an assignment like
  ``values = {key: build(key) for key in keys}`` now sorts after the ``build`` function
  it calls instead of ahead of it (which raised ``NameError``). A comprehension inside a
  function body stays deferred and still imposes no ordering.

********************
 0.2.0 (2026/06/14)
********************

**Added**

- Sort module- and class-level assignments. Within every scope the order is now
  assignments, then classes, then functions/methods, so methods always follow nested
  classes and assignments are grouped at the top. Assignments are split into uppercase
  ``CONSTANTS`` first and then other variables; each group sorts with a leading
  underscore first (so ``__dunder__`` and ``_private`` precede public names), and
  dependencies are respected (``B = A + 1`` stays after ``A``). As a result,
  module-level functions now sort after module-level classes. The attribute order of
  enums, dataclasses, and ``NamedTuple``/``TypedDict`` classes is preserved; the base or
  decorator is resolved through ``QualifiedNameProvider`` so aliased imports (``from
  enum import IntEnum as IE``) are recognized.
- Keep blank-line spacing with its position rather than the moved definition, so
  reordering no longer drags a blank line onto a different statement (for example the
  blank line after a class docstring stays at the top of the block). Comment lines that
  sit directly above a definition still travel with it.
- Keep an augmented assignment anchored to the constant it augments, so ``__all__ +=
  extra`` stays directly after ``__all__ = [...]`` instead of being left behind as a
  fixed barrier when another assignment sorts between them.
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

- Ignore a name used only in a lazy annotation (under ``from __future__ import
  annotations``) when ordering definitions, since the annotation is never evaluated at
  runtime and imposes no real dependency. A forward reference in an annotation (for
  example ``nxt: list[Instr]`` where ``Instr`` is a type-alias union of classes defined
  later) previously forged a false dependency cycle that could hoist the runtime alias
  above the classes it unions and raise ``NameError``.
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
