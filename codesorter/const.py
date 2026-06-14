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
ORDER_SENSITIVE_DECORATORS: frozenset[str] = frozenset({"dataclass", "define", "frozen", "mutable", "attrs"})
PLAIN_DECORATOR_PARTS = 1

PROPERTY_DECORATOR_PARTS = 2

__version__ = "0.2.1"
