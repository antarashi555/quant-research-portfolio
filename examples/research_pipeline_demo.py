"""Small end-to-end research *demonstration* using synthetic data only.

No live data, network, broker, LLM API, or private quant-research-core code.
Standard library only (Python >= 3.10). Not an investment tool.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SPEC = HERE / "data" / "strategy.json"
DEFAULT_DATA = HERE / "data" / "synthetic_bars.csv"
INITIAL_CASH = 1000.0


@dataclass(frozen=True)
class Bar:
    day: date
    available: date
    symbol: str
    open: float
    close: float


def load_bars(path: Path) -> list[Bar]:
    with path.open(newline="", encoding="utf-8") as stream:
        records = list(csv.DictReader(stream))
    if len(records) < 8:
        raise ValueError("at least eight observations required")
    bars = []
    for row in records:
        day, available = date.fromisoformat(row["date"]), date.fromisoformat(row["available_date"])
        open_price, close_price = float(row["open"]), float(row["close"])
        if available < day:
            raise ValueError("data cannot become available before its event")
        if not all(math.isfinite(x) and x > 0 for x in (open_price, close_price)):
            raise ValueError("prices must be positive and finite")
        bars.append(Bar(day, available, row["symbol"], open_price, close_price))
    if any(bars[i].day >= bars[i + 1].day for i in range(len(bars) - 1)):
        raise ValueError("dates must be strictly increasing")
    if len({bar.symbol for bar in bars}) != 1:
        raise ValueError("demo expects one synthetic symbol")
    return bars


def load_spec(path: Path, bars: list[Bar]) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    required = {"strategy_id", "hypothesis", "symbol", "lookback", "cost_bps", "train_end", "test_end"}
    if not isinstance(spec, dict) or set(spec) != required:
        raise ValueError("unexpected or missing strategy fields")
    if not all(isinstance(spec[key], str) and spec[key].strip() for key in
               ("strategy_id", "hypothesis", "symbol")):
        raise ValueError("strategy labels must be non-empty strings")
    if type(spec["lookback"]) is not int or not 2 <= spec["lookback"] <= len(bars) - 2:
        raise ValueError("invalid lookback")
    if type(spec["cost_bps"]) not in (int, float) or not math.isfinite(spec["cost_bps"]) or not 0 <= spec["cost_bps"] <= 500:
        raise ValueError("invalid cost_bps")
    if spec["symbol"] != bars[0].symbol:
        raise ValueError("symbol mismatch")
    train_end, test_end = date.fromisoformat(spec["train_end"]), date.fromisoformat(spec["test_end"])
    dates = [bar.day for bar in bars]
    if not (dates[0] < train_end < test_end < dates[-1]):
        raise ValueError("require nonempty ordered train, test, holdout intervals")
    if train_end not in dates or test_end not in dates:
        raise ValueError("split boundaries must fall on dataset dates")
    return spec


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PITView:
    """Return only closes published at the decision date; log *actual reads*."""

    def __init__(self, bars: list[Bar]):
        self.bars = bars
        self.access_log: list[dict] = []

    def recent(self, as_of: date, size: int) -> list[Bar]:
        available = [b for b in self.bars if b.day <= as_of and b.available <= as_of]
        chosen = available[-size:]
        for bar in chosen:
            self.record(as_of, bar)
        return chosen

    def record(self, as_of: date, bar: Bar) -> None:
        self.access_log.append({
            "decision_date": as_of.isoformat(),
            "event_date": bar.day.isoformat(),
            "available_date": bar.available.isoformat(),
        })


def simulate(bars: list[Bar], spec: dict, inject_leak: bool = False) -> dict:
    """Signal from published closes at date t; execution at date t+1 OPEN."""
    pit = PITView(bars)
    cash, shares = INITIAL_CASH, 0.0
    rate = spec["cost_bps"] / 10000.0
    trades = []
    equity = [{"date": bars[0].day.isoformat(), "equity": INITIAL_CASH}]
    injected = False

    for i, bar in enumerate(bars[:-1]):
        history = pit.recent(bar.day, spec["lookback"])
        if len(history) == spec["lookback"]:
            if inject_leak and not injected:
                # Demonstrate an unsafe implementation bypassing PITView.
                # The *independent* audit must detect this future observation.
                future_bar = bars[i + 1]
                pit.record(bar.day, future_bar)
                history[-1] = future_bar
                injected = True
            average = sum(item.close for item in history) / len(history)
            target = 1 if history[-1].close > average else 0
            execution = bars[i + 1]
            if target and shares == 0:
                shares = cash / (execution.open * (1.0 + rate))  # purchase + fee use the entire cash budget
                fee = shares * execution.open * rate
                cash = 0.0
                side = "BUY"
            elif not target and shares > 0:
                fee = shares * execution.open * rate
                cash = shares * execution.open - fee
                shares = 0.0
                side = "SELL"
            else:
                side = None
            if side:
                trades.append({
                    "side": side, "decision_date": bar.day.isoformat(),
                    "execution_date": execution.day.isoformat(),
                    "open_price": execution.open, "fee": round(fee, 8),
                })
        next_bar = bars[i + 1]
        equity.append({
            "date": next_bar.day.isoformat(),
            "equity": round(cash + shares * next_bar.close, 8),
        })

    return {"access_log": pit.access_log, "trades": trades, "equity_curve": equity}


def audit(bars: list[Bar], execution: dict, spec: dict) -> list[str]:
    """Check *recorded* reads and fills, not missing logs or signal calculations."""
    issues = []
    by_day = {bar.day.isoformat(): bar for bar in bars}
    dates = [bar.day.isoformat() for bar in bars]
    for n, access in enumerate(execution["access_log"], 1):
        original = by_day.get(access["event_date"])
        if original is None or original.available.isoformat() != access["available_date"]:
            issues.append(f"read {n}: unknown or modified source record")
            continue
        if (access["event_date"] > access["decision_date"]
                or access["available_date"] > access["decision_date"]):
            issues.append(f"read {n}: future/unpublished observation accessed")
    for n, trade in enumerate(execution["trades"], 1):
        if trade["decision_date"] not in dates or trade["execution_date"] not in dates:
            issues.append(f"trade {n}: unknown timestamp")
            continue
        ix = dates.index(trade["decision_date"])
        if ix + 1 >= len(dates) or dates[ix + 1] != trade["execution_date"]:
            issues.append(f"trade {n}: not executed on next bar")
        bar = by_day[trade["execution_date"]]
        if not math.isclose(bar.open, trade["open_price"], rel_tol=0, abs_tol=1e-9):
            issues.append(f"trade {n}: execution price does not match next open")
        if trade["fee"] < 0:
            issues.append(f"trade {n}: negative transaction cost")
    if not execution["access_log"]:
        issues.append("no PIT access evidence")
    return issues


def segment_metrics(curve: list[dict], spec: dict) -> dict:
    """Illustrative split returns; no optimization or statistical significance."""
    partitions = {"train": [], "test": [], "holdout": []}
    for row in curve:
        d = row["date"]
        bucket = "train" if d <= spec["train_end"] else ("test" if d <= spec["test_end"] else "holdout")
        partitions[bucket].append(row)
    baseline = INITIAL_CASH
    summary = {}
    for label, rows in partitions.items():
        if not rows:
            raise ValueError(f"empty {label} split")
        final_equity = rows[-1]["equity"]
        summary[label] = {
            "observations": len(rows),
            "end_date": rows[-1]["date"],
            "return_pct": round(100 * (final_equity / baseline - 1), 4),
        }
        baseline = final_equity
    return summary


def run_pipeline(spec_path: Path = DEFAULT_SPEC, data_path: Path = DEFAULT_DATA,
                 inject_leak: bool = False) -> dict:
    bars = load_bars(data_path)
    spec = load_spec(spec_path, bars)
    execution = simulate(bars, spec, inject_leak=inject_leak)
    findings = audit(bars, execution, spec)
    status = "REJECTED" if findings else "REVIEW_REQUIRED"
    report = {
        "demo": "synthetic-research-pipeline-v1",
        "hypothesis": spec["hypothesis"],
        "strategy_id": spec["strategy_id"],
        "source_hashes": {"spec_sha256": fingerprint(spec_path), "data_sha256": fingerprint(data_path)},
        "assumptions": {"initial_cash": INITIAL_CASH, "cost_bps": spec["cost_bps"],
                        "signal": "close above trailing mean of PIT-available closes",
                        "execution": "next bar open", "leak_injection": inject_leak},
        "audit": {"passed": not findings, "findings": findings,
                  "reads_checked": len(execution["access_log"])},
        "status": status,
        "manual_review_required": True,
        "stats": segment_metrics(execution["equity_curve"], spec),
        "final_equity": execution["equity_curve"][-1]["equity"],
        "trade_count": len(execution["trades"]),
        "trades": execution["trades"],
        "access_log": execution["access_log"],
        "equity_curve": execution["equity_curve"],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=Path("artifacts/demo-report.json"))
    parser.add_argument("--inject-leak", action="store_true",
                        help="intentionally read unpublished data: audit must reject the run")
    args = parser.parse_args()
    try:
        report = run_pipeline(args.spec, args.data, args.inject_leak)
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"INPUT ERROR: {exc}\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(f"STATUS: {report['status']}")
    print(f"Audit: {report['audit']['reads_checked']} reads, {len(report['audit']['findings'])} findings")
    for label, metric in report["stats"].items():
        print(f"{label}: {metric['return_pct']:+.4f}% ({metric['observations']} bars)")
    print(f"Trades: {report['trade_count']}; final synthetic equity: {report['final_equity']:.2f}")
    print(f"Report: {args.out}")
    if report["status"] == "REJECTED":
        for finding in report["audit"]["findings"]:
            print(f"  REJECTED: {finding}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
