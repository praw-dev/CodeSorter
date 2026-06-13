"""Command-line interface for the code sorter tool."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
import libcst as cst
import libcst.tool
import pathspec
from libcst.codemod import CodemodContext

from codesorter.const import DEFAULT_EXCLUDES
from codesorter.sort_code import SortCodeCommand

if TYPE_CHECKING:
    from pathspec.pattern import Pattern


def _check_files(files: list[str]) -> int:
    """Run the sort codemod in-process and report files that would change."""
    changed: list[str] = []
    failed: list[str] = []
    for path in files:
        try:
            source = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            click.echo(f"{path}: read error: {exc}", err=True)
            failed.append(path)
            continue
        try:
            new_tree = SortCodeCommand(CodemodContext()).transform_module(cst.parse_module(source))
        except Exception as exc:  # noqa: BLE001
            click.echo(f"{path}: transform error: {exc}", err=True)
            failed.append(path)
            continue
        if new_tree.code != source:
            changed.append(path)
            click.echo(f"Would reorder: {path}", err=True)
    if changed or failed:
        click.echo(
            f"{len(changed)} file(s) would be reordered, {len(failed)} file(s) failed.",
            err=True,
        )
        return 1
    return 0


def _collect_files(
    paths: tuple[str, ...],
    excludes: set[str],
    *,
    honor_gitignore: bool,
) -> list[str]:
    """Expand the given paths into a sorted, de-duplicated list of .py files."""
    seen: set[Path] = set()
    files: list[str] = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            click.echo(f"Path not found: {raw}", err=True)
            sys.exit(2)
        if path.is_file():
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                files.append(str(path))
            continue

        ignore_specs = _load_gitignore_specs(path, excludes) if honor_gitignore else []

        for candidate in sorted(path.rglob("*.py")):
            relative_parts = candidate.relative_to(path).parts
            if any(part in excludes for part in relative_parts):
                continue
            if _matches_gitignore(candidate, ignore_specs):
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(str(candidate))
    return files


def _load_gitignore_specs(
    root: Path,
    excludes: set[str],
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


@click.command(context_settings={"show_default": True})
@click.help_option("-h", "--help")
@click.option(
    "-c",
    "--check",
    is_flag=True,
    help="Don't write files; exit non-zero if any file would be reordered.",
)
@click.option(
    "-j",
    "--jobs",
    type=int,
    help="Number of jobs to use when processing files.",
)
@click.option(
    "-s",
    "--show-successes",
    is_flag=True,
    help="Print files successfully sorted with no warnings.",
)
@click.option(
    "-u",
    "--unified-diff",
    is_flag=True,
    help="Output unified diff instead of contents.",
)
@click.option(
    "-e",
    "--exclude",
    "extra_excludes",
    multiple=True,
    metavar="NAME",
    help="Directory name to skip when walking paths. May be passed multiple times.",
)
@click.option(
    "--no-default-excludes",
    is_flag=True,
    help="Disable the built-in directory excludes (.git, .venv, __pycache__, build, dist, ...).",
)
@click.option(
    "--no-gitignore",
    is_flag=True,
    help="Do not honor .gitignore files when walking paths.",
)
@click.argument(
    "paths",
    nargs=-1,
)
def main(
    check: bool,
    jobs: int | None,
    show_successes: bool,
    unified_diff: bool,
    extra_excludes: tuple[str, ...],
    no_default_excludes: bool,
    no_gitignore: bool,
    paths: tuple[str, ...],
) -> None:
    """Sort Python code in the specified package or file.

    This tool analyzes Python code and sorts classes and functions based on their
    dependencies and relationships.

    """
    if not paths:
        paths = (".",)

    excludes = set(extra_excludes)
    if not no_default_excludes:
        excludes.update(DEFAULT_EXCLUDES)

    files = _collect_files(paths, excludes, honor_gitignore=not no_gitignore)
    if not files:
        click.echo("No Python files to sort.", err=True)
        return

    if check:
        sys.exit(_check_files(files))

    argv = [
        "codemod",
        "-x",
        "codesorter.sort_code.SortCodeCommand",
        *files,
    ]

    if unified_diff:
        argv.append("--unified-diff")

    if show_successes:
        argv.append("--show-successes")

    if jobs is not None:
        argv.extend(["--jobs", str(jobs)])

    sys.exit(libcst.tool.main("codesorter", argv))
