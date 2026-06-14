"""Command-line interface for the code sorter tool."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import libcst as cst
import pathspec
from libcst.codemod import CodemodContext, parallel_exec_transform_with_prettyprint

from codesorter.const import DEFAULT_EXCLUDES
from codesorter.sort_code import SortCodeCommand

if TYPE_CHECKING:
    from pathspec.pattern import Pattern


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the code sorter CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Sort Python code in the specified package or file. This tool analyzes "
            "Python code and sorts classes and functions based on their dependencies "
            "and relationships."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        prog="codesorter",
    )
    parser.add_argument(
        "-c",
        "--check",
        action="store_true",
        help="Don't write files; exit non-zero if any file would be reordered.",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        help="Number of jobs to use when processing files.",
        type=int,
    )
    parser.add_argument(
        "-s",
        "--show-successes",
        action="store_true",
        help="Print files successfully sorted with no warnings.",
    )
    parser.add_argument(
        "-u",
        "--unified-diff",
        action="store_true",
        help="Output unified diff instead of contents.",
    )
    parser.add_argument(
        "-e",
        "--exclude",
        action="append",
        default=[],
        dest="extra_excludes",
        help="Directory name to skip when walking paths. May be passed multiple times.",
        metavar="NAME",
    )
    parser.add_argument(
        "--no-default-excludes",
        action="store_true",
        help="Disable the built-in directory excludes (.git, .venv, __pycache__, build, dist, ...).",
    )
    parser.add_argument(
        "--no-gitignore",
        action="store_true",
        help="Do not honor .gitignore files when walking paths.",
    )
    parser.add_argument(
        "paths",
        help="Files or directories to sort. Defaults to the current directory.",
        nargs="*",
    )
    return parser


def _check_files(*, files: list[str]) -> int:
    """Run the sort codemod in-process and report files that would change."""
    changed: list[str] = []
    failed: list[str] = []
    for path in files:
        try:
            source = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(f"{path}: read error: {exc}\n")
            failed.append(path)
            continue
        try:
            new_tree = SortCodeCommand(CodemodContext()).transform_module(cst.parse_module(source))
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"{path}: transform error: {exc}\n")
            failed.append(path)
            continue
        if new_tree.code != source:
            changed.append(path)
            sys.stderr.write(f"Would reorder: {path}\n")
    if changed or failed:
        sys.stderr.write(
            f"{len(changed)} file(s) would be reordered, {len(failed)} file(s) failed.\n",
        )
        return 1
    return 0


def _collect_files(
    *,
    excludes: set[str],
    honor_gitignore: bool,
    parser: argparse.ArgumentParser,
    paths: tuple[str, ...],
) -> list[str]:
    """Expand the given paths into a sorted, de-duplicated list of .py files."""
    seen: set[Path] = set()
    files: list[str] = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            parser.error(f"Path not found: {raw}")
        if path.is_file():
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                files.append(str(path))
            continue

        ignore_specs = _load_gitignore_specs(excludes=excludes, root=path) if honor_gitignore else []

        for candidate in sorted(path.rglob("*.py")):
            relative_parts = candidate.relative_to(path).parts
            if any(part in excludes for part in relative_parts):
                continue
            if _matches_gitignore(candidate=candidate, specs=ignore_specs):
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(str(candidate))
    return files


def _load_gitignore_specs(
    *,
    excludes: set[str],
    root: Path,
) -> list[tuple[Path, pathspec.PathSpec[Pattern]]]:
    """Collect (anchor_dir, spec) for every .gitignore at or below root.

    Each spec is interpreted relative to its containing directory, matching git's own
    behavior with nested .gitignore files.

    """
    specs: list[tuple[Path, pathspec.PathSpec[Pattern]]] = []
    for gitignore in root.rglob(".gitignore"):
        if not gitignore.is_file():
            continue
        if any(part in excludes for part in gitignore.relative_to(root).parts):
            continue
        lines = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
        spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)
        specs.append((gitignore.parent, spec))
    return specs


def _matches_gitignore(
    *,
    candidate: Path,
    specs: list[tuple[Path, pathspec.PathSpec[Pattern]]],
) -> bool:
    """Return True if any covering .gitignore matches the candidate file."""
    for anchor, spec in specs:
        try:
            rel = candidate.relative_to(anchor)
        except ValueError:
            continue
        if spec.match_file(str(rel)):
            return True
    return False


def main(*, argv: list[str] | None = None) -> None:
    """Sort Python code in the specified package or file."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    paths: tuple[str, ...] = tuple(args.paths) or (".",)

    excludes = set(args.extra_excludes)
    if not args.no_default_excludes:
        excludes.update(DEFAULT_EXCLUDES)

    files = _collect_files(
        excludes=excludes,
        honor_gitignore=not args.no_gitignore,
        parser=parser,
        paths=paths,
    )
    if not files:
        parser.error("No Python files to sort.")

    if args.check:
        sys.exit(_check_files(files=files))

    # Format with ruff so downstream projects need no ``.libcst.codemod.yaml`` (the
    # libcst codemod tool would otherwise default to black).
    result = parallel_exec_transform_with_prettyprint(
        SortCodeCommand,
        files,
        format_code=True,
        formatter_args=["ruff", "format", "-"],
        jobs=args.jobs,
        repo_root=".",
        show_successes=args.show_successes,
        unified_diff=5 if args.unified_diff else None,
    )
    sys.stderr.write(f"Finished codemodding {result.successes + result.skips + result.failures} files!\n")
    sys.stderr.write(f" - Transformed {result.successes} files successfully.\n")
    sys.stderr.write(f" - Skipped {result.skips} files.\n")
    sys.stderr.write(f" - Failed to codemod {result.failures} files.\n")
    sys.exit(1 if result.failures > 0 else 0)
