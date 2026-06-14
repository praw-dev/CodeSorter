"""The SortCodeCommand libcst codemod that reorders classes, methods, and functions."""

from __future__ import annotations

import enum
import heapq
from collections import defaultdict
from enum import auto
from typing import TYPE_CHECKING, Protocol, TypeVar

import libcst as cst
from libcst import matchers as m
from libcst import metadata as md
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from typing_extensions import Self

_PROPERTY_DECORATOR_PARTS = 2
_PLAIN_DECORATOR_PARTS = 1


def _gen_unique_name(node: cst.ClassDef | cst.FunctionDef) -> str:
    parts = [node.name.value]
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


# The bound is a forward reference so this assignment does not depend on the source
# position of ``_Commaed`` (which CodeSorter may reorder relative to this statement).
_CommaT = TypeVar("_CommaT", bound="_Commaed")


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
        determines positional binding.

        """
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

    METADATA_DEPENDENCIES = (md.ScopeProvider,)

    @property
    def in_class(self) -> bool:
        """Return True while the visitor is inside a class body."""
        return bool(self._class_depth)

    @in_class.setter
    def in_class(self, value: bool) -> None:
        if value:
            self._class_depth += 1
        elif self._class_depth > 0:
            self._class_depth -= 1
        else:
            self._class_depth = 0

    def __init__(self, context: CodemodContext) -> None:
        """Initialize per-run state used while collecting and sorting nodes."""
        super().__init__(context)
        self._counter = 0
        self._class_depth = 0
        self.original_nodes: dict[str, cst.CSTNode] = {}
        self.dependencies: defaultdict[str, set[str]] = defaultdict(set)
        self.dependents: defaultdict[str, set[str]] = defaultdict(set)

    def _dependency_edges(
        self,
        items: list[cst.ClassDef | cst.FunctionDef],
    ) -> tuple[list[set[int]], list[int]]:
        """Build the in-group dependency edges as ``(dependents, indegree)`` by index.

        ``dependents[i]`` holds the indexes that depend on ``items[i]`` and
        ``indegree[i]`` counts the in-group dependencies of ``items[i]``. Only edges
        between siblings in ``items`` are kept; references to names defined elsewhere
        impose no ordering.

        """
        name_to_indexes: defaultdict[str, list[int]] = defaultdict(list)
        for index, item in enumerate(items):
            name_to_indexes[item.name.value].append(index)
        dependents: list[set[int]] = [set() for _ in items]
        indegree = [0] * len(items)
        for index, item in enumerate(items):
            for dependency in self.dependencies.get(item.name.value, ()):
                for dependency_index in name_to_indexes.get(dependency, ()):
                    if dependency_index != index and index not in dependents[dependency_index]:
                        dependents[dependency_index].add(index)
                        indegree[index] += 1
        return dependents, indegree

    def _get_dependencies(  # noqa: C901
        self,
        node: cst.ClassDef | cst.FunctionDef,
    ) -> tuple[list[str], md.Scope]:
        original = self.original_nodes.get(_gen_unique_name(node))
        meta = None if original is None else self.get_metadata(md.ScopeProvider, original, None)
        if meta is None:
            msg = f"missing scope metadata for {node.name.value!r}"
            raise ValueError(msg)
        dependencies: set[str] = set()
        if isinstance(meta, (md.ClassScope, md.GlobalScope)):

            def _outer_scope(scope: object) -> bool:
                return isinstance(scope, (md.ClassScope, md.GlobalScope)) or (
                    isinstance(scope, md.ClassScope) and scope.parent != meta
                )

            for found in self.extractall(
                node,
                m.SaveMatchedNode(
                    m.Name(
                        metadata=m.MatchMetadataIfTrue(md.ScopeProvider, _outer_scope),
                        value=m.DoesNotMatch(node.name.value),
                    ),
                    "name",
                ),
            ):
                try:
                    node_name = cst.ensure_type(found["name"], cst.Name).value
                    is_import = isinstance(
                        next(iter(meta.assignments[node_name])),
                        md.ImportAssignment,
                    )
                    if is_import:
                        continue
                    is_global_scope = False
                    for access in meta[node_name]:
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
                        dependencies.add(node_name)
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
                                        value=m.DoesNotMatch(node.name.value),
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

    def _get_replacements(
        self,
        items: list[cst.ClassDef | cst.FunctionDef],
    ) -> dict[str, cst.ClassDef | cst.FunctionDef]:
        return {_gen_unique_name(old): new for old, new in zip(items, self._sorted_items(items), strict=True)}

    def _node_sort_key(
        self,
        node: cst.ClassDef | cst.FunctionDef,
    ) -> tuple[bool, MethodType, FixtureType, bool, str, PropertyType]:
        is_class = self.matches(node, m.ClassDef())
        method_type = MethodType.na
        fixture_type = FixtureType.na
        node_name = node.name.value
        property_type = PropertyType.na
        if not is_class:
            method_type = MethodType.instance
            for outer_decorator in node.decorators:
                decorator = outer_decorator.decorator
                decorator_parts = [cst.ensure_type(part, cst.Name).value for part in self.findall(decorator, m.Name())]
                if len(decorator_parts) == _PROPERTY_DECORATOR_PARTS:
                    decorator_type, accessor = decorator_parts
                    if decorator_type == node.name.value:
                        method_type = MethodType.property
                        property_type = PropertyType[accessor]
                if len(decorator_parts) == _PLAIN_DECORATOR_PARTS:
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
            not is_class if self.in_class else is_class,
            method_type,
            fixture_type,
            *_name_sort_key(node_name),
            property_type,
        )

    def _resolve_dependents(self, node: cst.ClassDef | cst.FunctionDef) -> None:
        dependencies, _ = self._get_dependencies(node)
        for dependency in dependencies:
            self.dependencies[node.name.value].add(dependency)
            for parent_dependency in self.dependencies[dependency]:
                self.dependencies[node.name.value].add(parent_dependency)

    def _sorted_items(
        self,
        items: list[cst.ClassDef | cst.FunctionDef],
    ) -> list[cst.ClassDef | cst.FunctionDef]:
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
        order: list[cst.ClassDef | cst.FunctionDef] = []
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
        """Sort the methods of the class body before returning the rewritten node."""
        items = [item for item in updated_node.body.body if isinstance(item, (cst.ClassDef, cst.FunctionDef))]
        updated_node = cst.ensure_type(
            updated_node.visit(SortingTransformer(self._get_replacements(items))), cst.ClassDef
        )
        self.in_class = False
        return updated_node

    def leave_Module(
        self,
        original_node: cst.Module,
        updated_node: cst.Module,
    ) -> cst.Module:
        """Sort the module-level definitions before returning the rewritten module."""
        items = [item for item in updated_node.body if isinstance(item, (cst.ClassDef, cst.FunctionDef))]
        updated_node = cst.ensure_type(
            updated_node.visit(SortingTransformer(self._get_replacements(items))), cst.Module
        )
        updated_node = cst.ensure_type(updated_node.visit(KeywordArgumentSorter()), cst.Module)
        self.original_nodes = {}
        return updated_node

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        """Record the class node and its dependencies before descending into it."""
        unique_name = _gen_unique_name(node)
        self.original_nodes[unique_name] = node
        self._resolve_dependents(node)
        self.in_class = True
        return True

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        """Record the function node and skip descending into its body."""
        unique_name = _gen_unique_name(node)
        self.original_nodes[unique_name] = node
        self._resolve_dependents(node)
        return False


class SortingTransformer(cst.CSTTransformer):
    """Apply a precomputed replacements map to swap nodes during a traversal."""

    def __init__(self, replacements: dict[str, cst.ClassDef | cst.FunctionDef]) -> None:
        """Store the replacements keyed by unique node name."""
        self.replacements = replacements
        super().__init__()

    def on_leave(
        self,
        original_node: cst.CSTNode,
        updated_node: cst.CSTNode,
    ) -> cst.CSTNode:
        """Swap matching class or function nodes for their replacement."""
        if isinstance(original_node, (cst.ClassDef, cst.FunctionDef)):
            return self.replacements.get(_gen_unique_name(original_node), updated_node)
        return updated_node
