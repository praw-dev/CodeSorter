#####################
 Pre-commit Workflow
#####################

CodeSorter sorts its own source code. Rather than pinning a published release, the
``codesorter`` hook in ``.pre-commit-config.yaml`` is configured as a local, self-hosted
hook so the repository is always sorted by the code on the current branch:

.. code-block:: yaml

    - hooks:
        - entry: codesorter
          id: codesorter
          language: system
          name: codesorter
          types: [python]
      repo: local

***************************
 Run hooks inside the venv
***************************

Because the hook uses ``language: system``, it runs the ``codesorter`` executable from
your environment instead of an isolated one pre-commit manages. CodeSorter then invokes
``ruff format`` as its formatter (configured in ``.libcst.codemod.yaml``). Both
``codesorter`` and ``ruff`` must therefore be on ``PATH`` when the hook runs.

Install the development environment and the git hook:

.. code-block:: bash

    uv sync
    uv run pre-commit install

Then run hooks with the project environment active, for example through ``uv run``:

.. code-block:: bash

    uv run pre-commit run --all-files

If you commit without the project environment on ``PATH`` (for example from an editor or
a shell where the venv is not activated), the hook fails with:

::

    Executable `codesorter` not found

Activate the virtual environment, or commit through ``uv run`` (``uv run git commit``),
so that ``codesorter`` and ``ruff`` are available. Continuous integration runs the same
hook through ``tox``, which installs both into its environment automatically.
