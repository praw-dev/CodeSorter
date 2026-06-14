######################
 Sorting and Barriers
######################

CodeSorter reorders the classes, functions, and assignments within a module or class
body, but only within a *segment* of consecutive definitions. Any statement that is not
a sortable definition acts as a **barrier**, and no definition is ever moved across one.

Barriers include bare expression statements (a function call on its own line such as
``sys.path.insert(0, str(ROOT))``), ``if`` / ``for`` / ``while`` / ``with`` blocks,
``import`` statements, and similar. A barrier splits the surrounding definitions into
independent segments, each sorted on its own.

********************
 Why barriers exist
********************

A statement sitting between definitions may depend on one of them, or be depended upon,
in ways that reordering would break. There are two cases, and only the first is visible
to a static tool:

1. The statement *references* a definition that would otherwise move after it:

   .. code-block:: python

       ROOT = Path(__file__).resolve().parent
       sys.path.insert(0, str(ROOT))  # uses ROOT

   If ``ROOT`` were sorted after the ``sys.path.insert`` call, the module would raise
   ``NameError`` on import.

2. A later definition depends on the statement's *side effect*, which no name reference
   reveals:

   .. code-block:: python

       configure_settings()
       DEFAULT_TIMEOUT = settings.get("timeout")  # reads what configure_settings() set up

   ``DEFAULT_TIMEOUT`` does not mention ``configure_settings`` by name, yet it must run
   after it. Moving the constant ahead of the call would silently read an unconfigured
   value — a wrong result rather than a crash.

Because side effects are opaque, CodeSorter cannot prove that crossing an arbitrary
statement is safe, so it treats every non-definition statement as a barrier.

**********************
 Relocating a barrier
**********************

The cost of this rule is small: a barrier that genuinely sits in the middle of a block
of definitions keeps the definitions on either side from sorting together. If a
statement legitimately should *not* separate your definitions — you know it has no
ordering relationship with them — move it yourself so it no longer sits between them.
For example, hoist a one-off call to the top of the module (just below the imports) or
to the bottom.

**Before** — the call sits between the classes, splitting them into two segments, so
``Alpha`` and ``Beta`` cannot sort together:

.. code-block:: python
    :class: codesorter-before

    class Beta: ...


    warnings.filterwarnings("ignore")


    class Alpha: ...

**After** — relocate the call above both classes; ``Alpha`` and ``Beta`` now form a
single segment and sort into order:

.. code-block:: python
    :class: codesorter-after

    warnings.filterwarnings("ignore")


    class Alpha: ...


    class Beta: ...

CodeSorter will not perform this move for you, precisely because it cannot prove the
move preserves behavior — only you know whether the statement is safe to relocate.
