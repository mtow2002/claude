"""Command-line entry point: ``portfolio-review <command> [options]``.

Subcommands are discovered automatically: every module in
``portfolio_review/commands/`` that defines ``register(subparsers)`` is loaded
and given the chance to add itself. To add a command, drop a new file in that
folder; this file never changes.
"""

from __future__ import annotations

import argparse
import importlib
import pkgutil
import sys
from typing import Sequence

from . import __version__
from . import commands as commands_pkg


def discover_commands(parser: argparse.ArgumentParser) -> None:
    """Import every commands/*.py module and call its register(subparsers)."""
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    for info in sorted(pkgutil.iter_modules(commands_pkg.__path__), key=lambda m: m.name):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{commands_pkg.__name__}.{info.name}")
        register = getattr(module, "register", None)
        if callable(register):
            register(subparsers)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="portfolio-review",
        description="Reproducible, point-in-time portfolio review.",
    )
    parser.add_argument("--version", action="version", version=f"portfolio-review {__version__}")
    discover_commands(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and dispatch. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.error(f"command {args.command} has no handler")
    try:
        return int(handler(args) or 0)
    except (ValueError, FileNotFoundError, FileExistsError, NotImplementedError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
