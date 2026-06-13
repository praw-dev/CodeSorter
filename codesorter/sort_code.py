"""The SortCodeCommand libcst codemod that reorders classes, methods, and functions."""

from __future__ import annotations

import enum
from collections import defaultdict
from enum import auto

import libcst as cst
from libcst import matchers as m
from libcst import metadata as md
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand

_PROPERTY_DECORATOR_PARTS = 2
_PLAIN_DECORATOR_PARTS = 1


def _gen_unique_name(node: cst.ClassDef | cst.FunctionDef) -> str:
    parts = [node.name.value]
    if isinstance(node, cst.ClassDef):
        items: tuple[cst.CSTNode, ...] = (*node.bases, *node.decorators, *node.keywords)
    else:
        items = (node,)
    for item in items:
        for name in m.findall(item, m.Name()):
            parts.append(cst.ensure_type(name, cst.Name).value)
    return ".".join(parts)


class DependencyType(enum.IntEnum):
    """Ordering buckets used to keep dependents after their dependencies."""

    not_required = auto()
    required = auto()


class FixtureType(enum.IntEnum):
    """Pytest fixture scopes used as a secondary sort key for fixture methods."""

    na = 0
    session_fixture = auto()
    package_fixture = auto()
    module_fixture = auto()
    class_fixture = auto()
    function_fixture = auto()


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

    def _get_dependencies(
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
                        value=m.DoesNotMatch(node.name.value),
                        metadata=m.MatchMetadataIfTrue(md.ScopeProvider, _outer_scope),
                    ),
                    "name",
                ),
            ):
                try:
                    node_name = cst.ensure_type(found["name"], cst.Name).value
                    is_import = isinstance(
                        list(meta.assignments[node_name])[0],  # noqa: RUF015
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
                except IndexError:
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
        return {
            _gen_unique_name(old): new for old, new in zip(items, sorted(items, key=self._node_sort_key), strict=True)
        }

    def _node_sort_key(
        self,
        node: cst.ClassDef | cst.FunctionDef,
    ) -> tuple[list[DependencyType], bool, MethodType, FixtureType, str, PropertyType]:
        _, meta = self._get_dependencies(node)
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
            [
                DependencyType.required
                if item.name in self.dependencies[node.name.value]
                else DependencyType.not_required
                for item in (
                    meta.assignments if not is_class and isinstance(meta, md.ClassScope) else meta.globals.assignments
                )
            ],
            not is_class if self.in_class else is_class,
            method_type,
            fixture_type,
            node_name,
            property_type,
        )

    def _resolve_dependents(self, node: cst.ClassDef | cst.FunctionDef) -> None:
        dependencies, _ = self._get_dependencies(node)
        for dependency in dependencies:
            self.dependencies[node.name.value].add(dependency)
            for parent_dependency in self.dependencies[dependency]:
                self.dependencies[node.name.value].add(parent_dependency)

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
