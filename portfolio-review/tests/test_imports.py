"""Every module must import cleanly. A function-scope import that only fails
at call time must fail here instead (lesson from the pipeline audit)."""

from __future__ import annotations

import importlib
import pkgutil

import portfolio_review


def test_every_module_imports():
    found = []
    for info in pkgutil.walk_packages(portfolio_review.__path__, "portfolio_review."):
        importlib.import_module(info.name)
        found.append(info.name)
    assert "portfolio_review.cli" in found
    assert "portfolio_review.commands.run" in found
    assert len(found) >= 20
