"""Standalone educational Point-in-Time (PIT) example using synthetic data.

This is NOT copied from the private quant-research-core implementation.
It does not place orders or make investment recommendations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable


@dataclass(frozen=True)
class Observation:
    symbol: str
    event_date: date
    available_date: date
    close: float

    def __post_init__(self) -> None:
        if self.close <= 0:
            raise ValueError("close must be positive")
        if self.available_date < self.event_date:
            raise ValueError("availability cannot precede event date")


class DataNotYetAvailable(ValueError):
    """Raised when a strategy tries to read information from the future."""


class PITView:
    """Expose only observations available as of a specified date."""

    def __init__(self, observations: Iterable[Observation]) -> None:
        self._observations = tuple(observations)

    def visible(self, as_of: date, symbol: str) -> tuple[Observation, ...]:
        return tuple(
            item for item in self._observations
            if item.symbol == symbol
            and item.event_date <= as_of
            and item.available_date <= as_of
        )

    def latest(self, as_of: date, symbol: str) -> Observation:
        candidates = self.visible(as_of, symbol)
        if not candidates:
            raise DataNotYetAvailable(
                f"No {symbol!r} observation available on {as_of.isoformat()}"
            )
        return max(candidates, key=lambda item: (item.event_date, item.available_date))


def synthetic_data() -> tuple[Observation, ...]:
    """Fake ticker/data; no provider market data is redistributed."""
    return (
        Observation("SYN", date(2026, 1, 5), date(2026, 1, 6), 100.0),
        Observation("SYN", date(2026, 1, 6), date(2026, 1, 7), 102.0),
        Observation("SYN", date(2026, 1, 7), date(2026, 1, 8), 99.0),
    )


def main() -> None:
    view = PITView(synthetic_data())
    for as_of in (date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)):
        try:
            obs = view.latest(as_of, "SYN")
            print(f"{as_of}: visible event={obs.event_date}, close={obs.close:.2f}")
        except DataNotYetAvailable as exc:
            print(f"{as_of}: {exc}")


if __name__ == "__main__":
    main()
