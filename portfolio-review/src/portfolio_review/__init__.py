"""portfolio_review: reproducible, point-in-time portfolio analysis.

The package is organised as a pipeline:

    config + holdings  ->  data providers (cached)  ->  analytics
                       ->  policy drift findings     ->  store + report

See docs/ARCHITECTURE.md for the full map.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("portfolio-review")
except PackageNotFoundError:  # running from a plain checkout without install
    __version__ = "0.1.0"

__all__ = ["__version__"]
