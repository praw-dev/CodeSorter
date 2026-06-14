###########
 Sort Code
###########

The :class:`.SortCodeCommand` is the libcst codemod that performs the reordering. The
``codesorter`` CLI applies it to the files you pass it; you can also use it directly as
a libcst codemod in your own tooling by constructing it with a ``CodemodContext`` and
calling ``transform_module`` (see the programmatic example in the README).

.. autoclass:: codesorter.sort_code.SortCodeCommand

The following enumerations define the secondary sort keys used to order members within a
class body.

.. autoclass:: codesorter.sort_code.MethodType

.. autoclass:: codesorter.sort_code.FixtureType

.. autoclass:: codesorter.sort_code.PropertyType
