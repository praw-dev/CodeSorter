"""The SortCodeCommand libcst codemod that reorders classes, methods, and functions."""

from __future__ import annotations

import enum
import heapq
import itertools
from collections import defaultdict
from enum import auto
from typing import TYPE_CHECKING, Protocol, TypeAlias, TypeVar, cast

import libcst as cst
from libcst import matchers as m
from libcst import metadata as md
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand

from codesorter.const import (
    ORDER_SENSITIVE_BASES,
    ORDER_SENSITIVE_CALLS,
    ORDER_SENSITIVE_DECORATORS,
    PLAIN_DECORATOR_PARTS,
    PROPERTY_DECORATOR_PARTS,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from typing_extensions import Self

# The bound is a forward reference so this assignment does not depend on the source
# position of ``_Commaed`` (which CodeSorter may reorder relative to this statement).
_CommaT = TypeVar("_CommaT", bound="_Commaed")

# A module- or class-body member that CodeSorter reorders: a class, a function, or a
# constant (a simple-name assignment wrapped in a SimpleStatementLine).
_Sortable: TypeAlias = "cst.ClassDef | cst.FunctionDef | cst.SimpleStatementLine"


class _Commaed(Protocol):
    """A comma-separated element (``Arg``, ``Param``, or dict element) that can be copied."""

    @property
    def comma(self) -> cst.Comma | cst.MaybeSentinel:
        """The trailing comma, kept attached to its slot when reordering."""
        ...

    def with_changes(self, **changes: object) -> Self:
        """Return a copy of the node with the given fields replaced."""
        ...


class FixtureType(enum.IntEnum):
    """Pytest fixture scopes used as a secondary sort key for fixture methods."""

    na = 0
    session_fixture = auto()
    package_fixture = auto()
    module_fixture = auto()
    class_fixture = auto()
    function_fixture = auto()


class KeywordArgumentSorter(cst.CSTTransformer):
    """Alphabetically sort keyword arguments, keyword-only parameters, and dict keys.

    In a call, keyword arguments are sorted and ``**`` unpackings moved to the end,
    while positional arguments and ``*`` unpackings stay put. In a dict literal, only
    runs of string-keyed entries are sorted, with ``**`` spreads and non-string keys
    acting as barriers to preserve last-wins merge semantics.

    """

    @staticmethod
    def _called_name(func: cst.BaseExpression) -> str | None:
        """Return the trailing name of a call target, or ``None`` if it is not a name.

        Resolves both a bare ``OrderedDict`` (``Name``) and a dotted
        ``collections.OrderedDict`` (``Attribute``) to ``"OrderedDict"``. An import
        alias is not followed, matching the suffix-based name matching used elsewhere
        for order-sensitive classes.

        """
        if isinstance(func, cst.Attribute):
            return func.attr.value
        if isinstance(func, cst.Name):
            return func.value
        return None

    @staticmethod
    def _sort_comma_runs(
        elements: Sequence[_CommaT],
        sortable: Callable[[_CommaT], bool],
        key: Callable[[_CommaT], tuple[int, bool, str]],
    ) -> list[_CommaT]:
        """Sort each maximal run of sortable comma-separated elements by ``key``.

        Elements for which ``sortable`` returns ``False`` act as barriers that are never
        moved, preserving the surrounding order. Commas stay attached to their slot so
        whitespace and any trailing comma are unchanged. The sort is stable, so elements
        with equal keys keep their relative order.

        """
        result = list(elements)
        index = 0
        while index < len(result):
            if not sortable(result[index]):
                index += 1
                continue
            end = index
            while end < len(result) and sortable(result[end]):
                end += 1
            run = result[index:end]
            if len(run) > 1:
                commas = [element.comma for element in run]
                ordered = sorted(run, key=key)
                result[index:end] = [item.with_changes(comma=commas[offset]) for offset, item in enumerate(ordered)]
            index = end
        return result

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Sort the keyword arguments of a call.

        ``**`` unpackings are sorted to the end of their run rather than treated as
        barriers: a call raises ``TypeError`` on any duplicate keyword regardless of
        order, so moving keyword arguments across a ``**`` cannot change the result.
        Positional arguments and ``*`` unpackings stay put because their order
        determines positional binding. Calls to an order-sensitive callable such as
        ``OrderedDict`` are left untouched, since their keyword-argument order is the
        iteration order and reordering it would change the resulting value.

        """
        if self._called_name(updated_node.func) in ORDER_SENSITIVE_CALLS:
            return updated_node
        return updated_node.with_changes(
            args=self._sort_comma_runs(
                updated_node.args,
                lambda arg: arg.keyword is not None or arg.star == "**",
                lambda arg: (
                    (1, *_name_sort_key(""))
                    if arg.keyword is None
                    else (0, *_name_sort_key(cst.ensure_type(arg.keyword, cst.Name).value))
                ),
            )
        )

    def leave_Dict(self, original_node: cst.Dict, updated_node: cst.Dict) -> cst.Dict:
        """Sort the string-keyed elements of a dict literal.

        Unlike a call, ``**`` spreads and non-string keys are barriers, because a dict
        merges last-wins, so reordering across them would change the resulting value.

        """
        return updated_node.with_changes(
            elements=self._sort_comma_runs(
                updated_node.elements,
                lambda element: (
                    isinstance(element, cst.DictElement)
                    and isinstance(element.key, cst.SimpleString)
                    and isinstance(element.key.evaluated_value, str)
                ),
                lambda element: (
                    0,
                    *_name_sort_key(
                        str(
                            cst.ensure_type(
                                cst.ensure_type(element, cst.DictElement).key, cst.SimpleString
                            ).evaluated_value
                        )
                    ),
                ),
            )
        )

    def leave_Parameters(self, original_node: cst.Parameters, updated_node: cst.Parameters) -> cst.Parameters:
        """Sort the keyword-only parameters of a function definition."""
        if len(updated_node.kwonly_params) <= 1:
            return updated_node
        return updated_node.with_changes(
            kwonly_params=self._sort_comma_runs(
                updated_node.kwonly_params, lambda _param: True, lambda param: (0, *_name_sort_key(param.name.value))
            )
        )


class MethodType(enum.IntEnum):
    """Method kinds used to sort methods within a class body."""

    na = 0
    abstractmethod = auto()
    autouse_fixture = auto()
    fixture = auto()
    staticmethod = auto()
    classmethod = auto()
    cachedproperty = auto()
    property = auto()
    contextmanager = auto()
    instance = auto()


class PropertyType(enum.IntEnum):
    """Property accessor kinds used to group getter/setter/deleter together."""

    na = 0
    getter = auto()
    setter = auto()
    deleter = auto()


class SortCodeCommand(VisitorBasedCodemodCommand, m.MatcherDecoratableTransformer):
    """Reorder module- and class-level definitions based on their dependencies."""

    # Add a description so that future codemodders can see what this does.
    DESCRIPTION: str = "Sorts code in project"

    METADATA_DEPENDENCIES = (md.ScopeProvider, md.QualifiedNameProvider)

    @staticmethod
    def _called_local_names(node: cst.SimpleStatementLine) -> set[str]:
        """Return the simple-name callees invoked in a constant's value.

        ``APP = App()`` calls ``App``; ``mod.factory()`` calls an attribute, which
        references an imported or external object and so imposes no in-module ordering
        and is ignored.

        """
        return {
            cst.ensure_type(cst.ensure_type(call, cst.Call).func, cst.Name).value
            for call in m.findall(node, m.Call(func=m.Name()))
        }

    @staticmethod
    def _is_sortable(member: cst.CSTNode, *, sort_constants: bool) -> bool:
        """Return True if ``member`` is a class, function, or sortable constant."""
        if isinstance(member, (cst.ClassDef, cst.FunctionDef)):
            return True
        return sort_constants and _constant_name(member) is not None

    def __init__(self, context: CodemodContext) -> None:
        """Initialize per-run state used while collecting and sorting nodes."""
        super().__init__(context)
        self.original_nodes: dict[str, cst.CSTNode] = {}
        self.dependencies: defaultdict[str, set[str]] = defaultdict(set)
        # ``body_globals[name]`` holds every module-global name referenced anywhere in a
        # node's body, including deferred references inside function and method bodies
        # that run only when the node is called. ``called_names[name]`` holds the local
        # names a constant assignment invokes (``App`` in ``APP = App()``). Together they
        # let ``_fold_runtime_dependencies`` order an import-time call after everything it
        # transitively reaches at runtime.
        self.body_globals: defaultdict[str, set[str]] = defaultdict(set)
        self.called_names: defaultdict[str, set[str]] = defaultdict(set)
        # When ``from __future__ import annotations`` is active every annotation is a
        # lazy string, so a name used only in an annotation imposes no runtime ordering.
        # ``_lazy_annotation_names`` holds the id of every such annotation Name node.
        self._lazy_annotation_names: frozenset[int] = frozenset()

    def _anchor_trailers(self, body: Sequence[cst.BaseStatement], *, sort_constants: bool) -> dict[int, int]:
        """Map each augmented-assignment line to the index of the constant it augments.

        An augmented assignment such as ``__all__ += other.__all__`` is anchored to the
        most recent constant assignment to the same name so it travels with that
        constant when the body is reordered, instead of being left behind as a fixed
        barrier. The anchor only applies when every statement between the two is itself
        movable, so a trailer is never lifted across an unrelated statement.

        """
        anchors: dict[int, int] = {}
        if not sort_constants:
            return anchors
        constant_index: dict[str, int] = {}
        for index, member in enumerate(body):
            if (constant := _constant_name(member)) is not None:
                constant_index[constant] = index
                continue
            name = _aug_assign_name(member)
            if name is None or name not in constant_index:
                continue
            anchor = constant_index[name]
            if all(
                self._is_sortable(body[between], sort_constants=sort_constants) or between in anchors
                for between in range(anchor + 1, index)
            ):
                anchors[index] = anchor
        return anchors

    def _candidate_names(self, expr: cst.BaseExpression) -> set[str]:
        """Return identifying names for a base or decorator expression.

        Includes the rightmost syntactic name and the last component of any resolved
        qualified name, so import aliases (``from enum import IntEnum as IE``) resolve
        back to the original name.

        """
        names: set[str] = set()
        if (rightmost := _rightmost_name(expr)) is not None:
            names.add(rightmost)
        names.update(
            qualified.name.rsplit(".", maxsplit=1)[-1]
            for qualified in self.get_metadata(md.QualifiedNameProvider, expr, frozenset())
        )
        return names

    def _dependency_edges(
        self,
        items: list[_Sortable],
    ) -> tuple[list[set[int]], list[int]]:
        """Build the in-group dependency edges as ``(dependents, indegree)`` by index.

        ``dependents[i]`` holds the indexes that depend on ``items[i]`` and
        ``indegree[i]`` counts the in-group dependencies of ``items[i]``. Only edges
        between siblings in ``items`` are kept; references to names defined elsewhere
        impose no ordering.

        """
        name_to_indexes: defaultdict[str, list[int]] = defaultdict(list)
        for index, item in enumerate(items):
            name_to_indexes[_sortable_name(item)].append(index)
        dependents: list[set[int]] = [set() for _ in items]
        indegree = [0] * len(items)

        def _add_edge(earlier: int, later: int) -> None:
            if earlier != later and later not in dependents[earlier]:
                dependents[earlier].add(later)
                indegree[later] += 1

        for index, item in enumerate(items):
            for dependency in self.dependencies.get(_sortable_name(item), ()):
                for dependency_index in name_to_indexes.get(dependency, ()):
                    _add_edge(dependency_index, index)
        # An assignment that rebinds a name also bound by a sibling (for example
        # ``def x`` followed by ``x = wraps(x)``) must keep its original position, since
        # the later binding wins at runtime and may reference the earlier one. Groups of
        # same-named methods (property getter/setter/deleter) are excluded — they carry
        # no assignment and are ordered safely by their sort key.
        for indexes in name_to_indexes.values():
            for earlier, later in itertools.pairwise(indexes):
                if isinstance(items[earlier], cst.SimpleStatementLine) or isinstance(
                    items[later], cst.SimpleStatementLine
                ):
                    _add_edge(earlier, later)
        return dependents, indegree

    def _fold_runtime_dependencies(self) -> None:
        """Order an import-time call after everything the call reaches at runtime.

        ``X = factory()`` only references ``factory`` syntactically, but executing it at
        import runs ``factory``'s body, so ``X`` must also follow every module-global
        that body uses (and, transitively, whatever those callees use). Without this an
        assignment can be hoisted above a function it needs and fail with ``NameError``
        at import. Definitions gain no edges from this, so it never forges a cycle
        between a class or function and its siblings.

        """
        runtime = {name: set(globals_) for name, globals_ in self.body_globals.items()}
        changed = True
        while changed:
            changed = False
            for reachable in runtime.values():
                additions = {
                    name for dependency in tuple(reachable) for name in runtime.get(dependency, ())
                } - reachable
                if additions:
                    reachable.update(additions)
                    changed = True
        for name, callees in self.called_names.items():
            for callee in callees:
                self.dependencies[name].update(runtime.get(callee, ()))

    def _get_dependencies(  # noqa: C901
        self,
        node: _Sortable,
    ) -> tuple[list[str], md.Scope]:
        node_name = _sortable_name(node)
        original = self.original_nodes.get(_gen_unique_name(node))
        meta = None if original is None else self.get_metadata(md.ScopeProvider, original, None)
        if meta is None:
            msg = f"missing scope metadata for {node_name!r}"
            raise ValueError(msg)
        dependencies: set[str] = set()
        if isinstance(meta, (md.ClassScope, md.GlobalScope)):

            def _outer_scope(scope: object) -> bool:
                # A comprehension at module or class level runs eagerly when the
                # definition executes, so a name used inside it is a real dependency.
                # Walk out through any comprehension scopes; a function scope in the
                # chain means the reference is deferred (a lambda or method body) and is
                # not a definition-time dependency.
                while isinstance(scope, md.ComprehensionScope):
                    scope = scope.parent
                return isinstance(scope, (md.ClassScope, md.GlobalScope))

            for found in self.extractall(
                node,
                m.SaveMatchedNode(
                    m.Name(
                        metadata=m.MatchMetadataIfTrue(md.ScopeProvider, _outer_scope),
                        value=m.DoesNotMatch(node_name),
                    ),
                    "name",
                ),
            ):
                try:
                    # A name used only in a lazy annotation (under ``from __future__
                    # import annotations``) is never evaluated at runtime, so it imposes
                    # no ordering and is ignored. This also avoids a forward reference in
                    # an annotation forging a false cycle with a real value-level edge.
                    if id(found["name"]) in self._lazy_annotation_names:
                        continue
                    name_node = cst.ensure_type(found["name"], cst.Name)
                    found_name = name_node.value
                    # A name bound at this class's own body level (an enum member or
                    # class variable) belongs to the class's namespace, so it must not
                    # forge a dependency on a same-named outer definition. Otherwise an
                    # enum member named like the module constant that aliases it (for
                    # example ``CACHE_MISS = _Sentinel.CACHE_MISS``) creates a false cycle
                    # that hoists the constant above the class it depends on. The scope
                    # must be ``node``'s own class scope; a name bound in the *enclosing*
                    # class (a sibling method an alias assignment references) is a real
                    # dependency and is kept.
                    name_scope = self.get_metadata(md.ScopeProvider, name_node, None)
                    if (
                        isinstance(name_scope, md.ClassScope)
                        and name_scope.node == node
                        and name_scope.assignments[found_name]
                    ):
                        continue
                    is_import = isinstance(
                        next(iter(meta.assignments[found_name])),
                        md.ImportAssignment,
                    )
                    if is_import:
                        continue
                    is_global_scope = False
                    for access in meta[found_name]:
                        if isinstance(access, md.Access) and access.is_annotation:
                            continue
                        if isinstance(access.scope, md.GlobalScope):
                            is_global_scope = True
                            break
                        if isinstance(access.scope, md.ClassScope):
                            if access.scope.node == node:
                                continue
                            is_global_scope = True
                            break
                    if is_global_scope:
                        dependencies.add(found_name)
                except StopIteration:
                    pass
            if self.matches(node, m.ClassDef()):
                for subclass in self.extractall(
                    node,
                    m.ClassDef(
                        bases=[
                            m.Arg(
                                value=m.SaveMatchedNode(
                                    m.Name(
                                        value=m.DoesNotMatch(node_name),
                                    ),
                                    "name",
                                )
                            ),
                        ]
                    ),
                ):
                    subclass_name = cst.ensure_type(subclass["name"], cst.Name).value
                    for assignment in meta.globals.assignments[subclass_name]:
                        if isinstance(assignment, (md.BuiltinAssignment, md.ImportAssignment)):
                            continue
                        dependencies.add(subclass_name)
        return list(dependencies), meta

    def _is_order_sensitive_class(self, node: cst.ClassDef) -> bool:
        """Return True if ``node`` is an enum, dataclass, or named tuple / typed dict.

        The attribute order of these classes is significant (enum values, generated
        ``__init__`` signatures), so their assignments are left in place. Names are
        resolved through import aliases via :class:`QualifiedNameProvider`; custom enum
        subclasses are still matched by an ``Enum``/``Flag`` name suffix.

        """
        for base in node.bases:
            if any(
                name in ORDER_SENSITIVE_BASES or name.endswith(("Enum", "Flag"))
                for name in self._candidate_names(base.value)
            ):
                return True
        for decorator in node.decorators:
            target = decorator.decorator
            target = target.func if isinstance(target, cst.Call) else target
            if self._candidate_names(target) & ORDER_SENSITIVE_DECORATORS:
                return True
        return False

    def _node_sort_key(  # noqa: C901
        self,
        node: _Sortable,
    ) -> tuple[int, int, MethodType, FixtureType, bool, str, PropertyType]:
        node_name = _sortable_name(node)
        if not isinstance(node, (cst.ClassDef, cst.FunctionDef)):
            # An assignment sorts ahead of classes and functions. Uppercase CONSTANTS sort
            # before other variables, and within each group a leading underscore sorts
            # first (so ``__dunder__`` and ``_private`` precede public names).
            constant_rank = 0 if node_name.isupper() else 1
            return (0, constant_rank, MethodType.na, FixtureType.na, *_name_sort_key(node_name), PropertyType.na)
        is_class = self.matches(node, m.ClassDef())
        category = 1 if is_class else 2
        method_type = MethodType.na
        fixture_type = FixtureType.na
        property_type = PropertyType.na
        if not is_class:
            method_type = MethodType.instance
            for outer_decorator in node.decorators:
                decorator = outer_decorator.decorator
                decorator_parts = [cst.ensure_type(part, cst.Name).value for part in self.findall(decorator, m.Name())]
                if len(decorator_parts) == PROPERTY_DECORATOR_PARTS:
                    decorator_type, accessor = decorator_parts
                    if decorator_type == node.name.value:
                        method_type = MethodType.property
                        property_type = PropertyType[accessor]
                if len(decorator_parts) == PLAIN_DECORATOR_PARTS:
                    decorator_type = decorator_parts[0]
                    if decorator_type == "property":
                        method_type = MethodType.property
                        property_type = PropertyType.getter
                    else:
                        method_type = MethodType.__members__.get(decorator_type, method_type)
                if self.matches(
                    decorator,
                    m.Attribute(attr=m.Name(value="fixture"), value=m.Name("pytest"))
                    | m.Call(func=m.Attribute(attr=m.Name(value="fixture"), value=m.Name("pytest"))),
                ):
                    scope_match = self.extract(
                        decorator,
                        m.Call(
                            args=[
                                m.ZeroOrMore(m.DoNotCare()),
                                m.OneOf(
                                    m.Arg(
                                        keyword=m.Name(value="scope"),
                                        value=m.SaveMatchedNode(m.SimpleString(), "scope"),
                                    )
                                ),
                                m.ZeroOrMore(m.DoNotCare()),
                            ]
                        ),
                    )
                    autouse = self.matches(
                        decorator,
                        m.Call(
                            args=[
                                m.ZeroOrMore(m.DoNotCare()),
                                m.OneOf(
                                    m.Arg(
                                        keyword=m.Name(value="autouse"),
                                        value=m.Name("True"),
                                    )
                                ),
                                m.ZeroOrMore(m.DoNotCare()),
                            ]
                        ),
                    )
                    fixture_type = FixtureType.function_fixture
                    if scope_match:
                        scope_value = cst.ensure_type(scope_match["scope"], cst.SimpleString).evaluated_value
                        fixture_type = FixtureType[f"{scope_value}_fixture"]
                    method_type = MethodType.autouse_fixture if autouse else MethodType.fixture
                elif isinstance(decorator, cst.Attribute) and isinstance(decorator.value, cst.Name):
                    method_type = MethodType.__members__.get(decorator.value.value, method_type)
        return (
            category,
            0,  # constant_rank is only meaningful for assignments
            method_type,
            fixture_type,
            *_name_sort_key(node_name),
            property_type,
        )

    def _reorder_segment(
        self,
        body: Sequence[cst.BaseStatement],
        new_body: list[cst.BaseStatement],
        *,
        anchor_indexes: list[int],
        trailers_of: dict[int, list[int]],
    ) -> None:
        """Reorder one barrier-free segment of sortable members in place within ``new_body``."""
        if not anchor_indexes:
            return
        positions: list[int] = []
        anchor_nodes: list[_Sortable] = []
        trailers_by_anchor: dict[int, list[cst.BaseStatement]] = {}
        for index in anchor_indexes:
            trailer_indexes = sorted(trailers_of.get(index, []))
            positions.append(index)
            positions.extend(trailer_indexes)
            anchor = cast("_Sortable", body[index])
            anchor_nodes.append(anchor)
            trailers_by_anchor[id(anchor)] = [body[trailer] for trailer in trailer_indexes]
        # Blank-line separators are positional: the n-th anchor in the segment keeps the
        # n-th separator. Trailers are excluded so they stay tight to their anchor.
        anchor_separators = [_split_leading_lines(node)[0] for node in anchor_nodes]
        trailer_ids = {id(trailer) for trailers in trailers_by_anchor.values() for trailer in trailers}
        flattened: list[cst.BaseStatement] = []
        for anchor in self._sorted_items(anchor_nodes):
            flattened.append(anchor)
            flattened.extend(trailers_by_anchor[id(anchor)])
        anchor_index = 0
        for position, member in zip(sorted(positions), flattened, strict=True):
            if id(member) in trailer_ids:
                new_body[position] = member
                continue
            _, attached = _split_leading_lines(member)
            new_body[position] = member.with_changes(leading_lines=[*anchor_separators[anchor_index], *attached])
            anchor_index += 1

    def _resolve_dependents(self, node: _Sortable) -> None:
        dependencies, _ = self._get_dependencies(node)
        name = _sortable_name(node)
        self.body_globals[name] = self._runtime_global_names(node)
        for dependency in dependencies:
            self.dependencies[name].add(dependency)
            for parent_dependency in self.dependencies[dependency]:
                self.dependencies[name].add(parent_dependency)

    def _runtime_global_names(self, node: _Sortable) -> set[str]:
        """Return every module-global name referenced anywhere within ``node``.

        Unlike :meth:`_get_dependencies`, this includes names used in nested function
        and method bodies, which run only when the node is called rather than when it is
        defined. Each name is resolved through its own scope, so a local that shadows a
        module global is correctly excluded.

        """
        own = _sortable_name(node)
        names: set[str] = set()
        for found in m.findall(node, m.Name()):
            name_node = cst.ensure_type(found, cst.Name)
            if id(name_node) in self._lazy_annotation_names or name_node.value == own:
                continue
            scope = self.get_metadata(md.ScopeProvider, name_node, None)
            if scope is None:
                continue
            try:
                assignments = scope[name_node.value]
            except KeyError:
                continue
            for assignment in assignments:
                if isinstance(assignment, (md.BuiltinAssignment, md.ImportAssignment)):
                    continue
                if isinstance(assignment.scope, md.GlobalScope):
                    names.add(name_node.value)
                    break
        return names

    def _sorted_body(
        self,
        body: Sequence[cst.BaseStatement],
        *,
        sort_constants: bool,
    ) -> list[cst.BaseStatement]:
        """Reorder the sortable members of a body, leaving every other statement in place.

        Classes and functions (and, when ``sort_constants`` is True, constant
        assignments) are reordered among the positions they already occupy, so
        surrounding statements keep their absolute position and act as barriers. An
        augmented assignment to a constant travels with that constant rather than acting
        as a barrier, so ``__all__ += ...`` stays adjacent to ``__all__ = [...]``.

        Blank-line spacing stays with each slot while comment lines travel with their
        statement, so reordering never shifts a blank line onto a different statement.

        Sortable members are only reordered within a segment of consecutive sortable
        members; any other statement (an import, a bare expression such as
        ``sys.path.insert(...)``, an ``if`` block) is a barrier that no definition may
        cross, since the barrier may depend on a definition beside it.

        """
        anchors = self._anchor_trailers(body, sort_constants=sort_constants)
        trailers_of: defaultdict[int, list[int]] = defaultdict(list)
        for trailer_index, anchor_index in anchors.items():
            trailers_of[anchor_index].append(trailer_index)
        new_body = list(body)
        segment: list[int] = []
        for index, member in enumerate(body):
            if index in anchors:
                continue  # a trailer, reordered together with its anchor
            if self._is_sortable(member, sort_constants=sort_constants):
                segment.append(index)
                continue
            self._reorder_segment(body, new_body, anchor_indexes=segment, trailers_of=trailers_of)
            segment = []
        self._reorder_segment(body, new_body, anchor_indexes=segment, trailers_of=trailers_of)
        return new_body

    def _sorted_items(
        self,
        items: list[_Sortable],
    ) -> list[_Sortable]:
        """Order siblings alphabetically while keeping each node after its dependencies.

        A priority topological sort is used: among the nodes whose in-group dependencies
        have all been emitted, the one with the smallest :meth:`._node_sort_key` is
        chosen next. Any dependency cycle is broken by releasing the smallest-key node
        still pending, so the function always returns every item exactly once.

        """
        keys = [self._node_sort_key(item) for item in items]
        dependents, indegree = self._dependency_edges(items)
        heap = [(keys[index], index) for index in range(len(items)) if indegree[index] == 0]
        heapq.heapify(heap)
        emitted = [False] * len(items)
        order: list[_Sortable] = []
        while len(order) < len(items):
            if not heap:
                # A dependency cycle remains; release the smallest-key pending node.
                stuck = min((index for index in range(len(items)) if not emitted[index]), key=keys.__getitem__)
                heapq.heappush(heap, (keys[stuck], stuck))
            _, index = heapq.heappop(heap)
            if emitted[index]:
                continue
            emitted[index] = True
            order.append(items[index])
            for dependent in dependents[index]:
                indegree[dependent] -= 1
                if indegree[dependent] == 0 and not emitted[dependent]:
                    heapq.heappush(heap, (keys[dependent], dependent))
        return order

    def leave_ClassDef(
        self,
        original_node: cst.ClassDef,
        updated_node: cst.ClassDef,
    ) -> cst.ClassDef:
        """Sort the members of the class body before returning the rewritten node."""
        body = updated_node.body
        if not isinstance(body, cst.IndentedBlock):
            return updated_node
        sort_constants = not self._is_order_sensitive_class(original_node)
        return updated_node.with_changes(
            body=body.with_changes(body=self._sorted_body(body.body, sort_constants=sort_constants))
        )

    def leave_Module(
        self,
        original_node: cst.Module,
        updated_node: cst.Module,
    ) -> cst.Module:
        """Sort the module-level definitions before returning the rewritten module."""
        self._fold_runtime_dependencies()
        updated_node = updated_node.with_changes(body=self._sorted_body(updated_node.body, sort_constants=True))
        updated_node = cst.ensure_type(updated_node.visit(KeywordArgumentSorter()), cst.Module)
        self.original_nodes = {}
        self.body_globals.clear()
        self.called_names.clear()
        return updated_node

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        """Record the class node and its dependencies before descending into it."""
        self.original_nodes[_gen_unique_name(node)] = node
        self._resolve_dependents(node)
        return True

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        """Record the function node and skip descending into its body."""
        self.original_nodes[_gen_unique_name(node)] = node
        self._resolve_dependents(node)
        return False

    def visit_Module(self, node: cst.Module) -> bool:
        """Record whether annotations are lazy before collecting dependencies.

        Under ``from __future__ import annotations`` every annotation Name node is a
        lazy forward reference, so it is collected here and ignored when building
        dependency edges (otherwise a forward reference in an annotation forges a false
        cycle).

        """
        future_annotations = bool(
            self.findall(
                node,
                m.ImportFrom(
                    module=m.Name("__future__"),
                    names=[m.ZeroOrMore(), m.ImportAlias(name=m.Name("annotations")), m.ZeroOrMore()],
                ),
            )
        )
        if future_annotations:
            self._lazy_annotation_names = frozenset(
                id(name)
                for annotation in self.findall(node, m.Annotation())
                for name in self.findall(annotation, m.Name())
            )
        return True

    def visit_SimpleStatementLine(self, node: cst.SimpleStatementLine) -> bool:
        """Record a constant assignment and its dependencies; skip everything else."""
        if _constant_name(node) is not None:
            self.original_nodes[_gen_unique_name(node)] = node
            self._resolve_dependents(node)
            self.called_names[_sortable_name(node)] = self._called_local_names(node)
        return False


def _aug_assign_name(node: cst.CSTNode) -> str | None:
    """Return the target name if ``node`` is a single augmented assignment, else None.

    An augmented assignment is a ``SimpleStatementLine`` holding exactly one
    ``AugAssign`` with a single ``Name`` target (for example ``__all__ += extra``).

    """
    if not isinstance(node, cst.SimpleStatementLine) or len(node.body) != 1:
        return None
    statement = node.body[0]
    if isinstance(statement, cst.AugAssign) and isinstance(statement.target, cst.Name):
        return statement.target.value
    return None


def _constant_name(node: cst.CSTNode) -> str | None:
    """Return the target name if ``node`` is a single simple-name assignment, else None.

    A "constant" is a ``SimpleStatementLine`` holding exactly one ``Assign`` with a
    single ``Name`` target or one ``AnnAssign`` with a ``Name`` target. Tuple targets,
    chained assignments, augmented assignments, attribute/subscript targets, imports,
    docstrings, and anything else are not constants and are left in place when sorting.

    """
    if not isinstance(node, cst.SimpleStatementLine) or len(node.body) != 1:
        return None
    statement = node.body[0]
    if isinstance(statement, cst.Assign):
        if len(statement.targets) == 1 and isinstance(statement.targets[0].target, cst.Name):
            return statement.targets[0].target.value
        return None
    if isinstance(statement, cst.AnnAssign) and isinstance(statement.target, cst.Name):
        return statement.target.value
    return None


def _gen_unique_name(node: cst.ClassDef | cst.FunctionDef | cst.SimpleStatementLine) -> str:
    parts = [_sortable_name(node)]
    if isinstance(node, cst.ClassDef):
        items: tuple[cst.CSTNode, ...] = (*node.bases, *node.decorators, *node.keywords)
    else:
        items = (node,)
    for item in items:
        parts.extend(cst.ensure_type(name, cst.Name).value for name in m.findall(item, m.Name()))
    return ".".join(parts)


def _name_sort_key(name: str) -> tuple[bool, str]:
    """Return an alphabetical sort key that orders ``_``-prefixed names first.

    A plain string sort places ``_`` (and dunders) after capitalized names because the
    underscore has a higher code point than ``A``-``Z``. Sorting on a leading-underscore
    flag first keeps private and dunder names grouped ahead of the public ones.

    """
    return (not name.startswith("_"), name)


def _rightmost_name(node: cst.BaseExpression) -> str | None:
    """Return the rightmost simple name of a base or decorator expression, if any."""
    if isinstance(node, cst.Call):
        node = node.func
    if isinstance(node, cst.Attribute):
        return node.attr.value
    if isinstance(node, cst.Name):
        return node.value
    return None


def _sortable_name(node: cst.ClassDef | cst.FunctionDef | cst.SimpleStatementLine) -> str:
    """Return the name used to sort and identify a class, function, or constant."""
    if isinstance(node, (cst.ClassDef, cst.FunctionDef)):
        return node.name.value
    return _constant_name(node) or ""


def _split_leading_lines(node: cst.CSTNode) -> tuple[list[cst.EmptyLine], list[cst.EmptyLine]]:
    """Split a node's leading lines into positional spacing and attached comments.

    The attached part is the trailing run of comment lines that sit directly above the
    statement with no blank line between them; the separator is everything before it.
    When statements are reordered the separator stays with the slot, so blank-line
    spacing is preserved, while the attached comments travel with their statement.

    """
    if not isinstance(node, (cst.SimpleStatementLine, cst.BaseCompoundStatement)):
        return [], []
    leading = list(node.leading_lines)
    split = len(leading)
    while split > 0 and leading[split - 1].comment is not None:
        split -= 1
    return leading[:split], leading[split:]
