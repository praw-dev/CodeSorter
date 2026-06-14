"""Package constants and version metadata."""

__version__ = "0.1.1.dev0"

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
