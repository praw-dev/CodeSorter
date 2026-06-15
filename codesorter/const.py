"""Package constants and version metadata."""

DEFAULT_EXCLUDES: tuple[str, ...] = (
    ".bzr",
    ".direnv",
    ".eggs",
    ".git",
    ".hg",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "__pypackages__",
    "build",
    "dist",
    "env",
    "node_modules",
    "venv",
)
# Bases and decorators that make a class body order-sensitive, so its attribute
# assignments must not be reordered (enum member order sets the values; dataclass and
# NamedTuple/TypedDict field order sets the generated signature).
ORDER_SENSITIVE_BASES: frozenset[str] = frozenset({
    "Enum",
    "IntEnum",
    "StrEnum",
    "Flag",
    "IntFlag",
    "ReprEnum",
    "NamedTuple",
    "TypedDict",
})
# Callables whose keyword-argument order is semantically significant, so their calls must
# not have keyword arguments reordered. ``OrderedDict(a=1, b=2)`` iterates in argument order,
# and ``OrderedDict(b=2, a=1)`` is a distinct (unequal) value, so the order must be preserved.
ORDER_SENSITIVE_CALLS: frozenset[str] = frozenset({"OrderedDict"})
ORDER_SENSITIVE_DECORATORS: frozenset[str] = frozenset({"dataclass", "define", "frozen", "mutable", "attrs"})
PLAIN_DECORATOR_PARTS = 1

PROPERTY_DECORATOR_PARTS = 2

__version__ = "0.2.8.dev0"
