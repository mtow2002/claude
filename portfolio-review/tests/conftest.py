"""Shared pytest fixtures. NO test here ever touches the network.

``csv_provider`` reads the synthetic CSVs under tests/fixtures/prices.
``counting_provider`` wraps it and counts calls, for cache tests.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from portfolio_review.data.csv_provider import CSVProvider

FIXTURES = Path(__file__).parent / "fixtures"
PRICES_DIR = FIXTURES / "prices"
AS_OF = date(2025, 9, 30)


class CountingProvider:
    """Delegates to an inner provider and counts how many real calls it made."""

    def __init__(self, inner):
        self.inner = inner
        self.name = inner.name
        self.price_calls = 0
        self.profile_calls = 0

    def prices(self, ticker, start, end, as_of):
        self.price_calls += 1
        return self.inner.prices(ticker, start, end, as_of)

    def profile(self, ticker, as_of):
        self.profile_calls += 1
        return self.inner.profile(ticker, as_of)


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def prices_dir() -> Path:
    return PRICES_DIR


@pytest.fixture
def as_of() -> date:
    return AS_OF


@pytest.fixture
def csv_provider() -> CSVProvider:
    return CSVProvider(PRICES_DIR)


@pytest.fixture
def counting_provider(csv_provider) -> CountingProvider:
    return CountingProvider(csv_provider)
