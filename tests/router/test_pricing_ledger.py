import datetime as dt
from pathlib import Path

import pytest

from ladder_harness.router.ledger import Ledger, summary
from ladder_harness.router.pricing import Pricing
from ladder_harness.router.types import Usage

ROOT = Path(__file__).resolve().parents[2]
PRICING = Pricing.load(ROOT / "config" / "pricing.yaml")


def test_flash_intro_and_list_prices():
    u = Usage(input=1_000_000, output=1_000_000, thinking=0, cached=0)
    assert PRICING.price("gemini-3.8-flash", u, dt.date(2026, 10, 1)) == pytest.approx(4.50)
    assert PRICING.price("gemini-3.8-flash", u, dt.date(2027, 2, 1)) == pytest.approx(9.00)
    assert PRICING.price_both("gemini-3.8-flash", u) == {"intro": pytest.approx(4.50), "list": pytest.approx(9.00)}


def test_opus_price_and_thinking_billed_as_output():
    u = Usage(input=10_000, output=1_000, thinking=2_000, cached=4_000)
    expected = (6_000 * 4.00 + 4_000 * 0.20 + 3_000 * 20.00) / 1e6
    assert PRICING.price("claude-opus-5-5", u, dt.date(2026, 10, 1)) == pytest.approx(expected)


def test_unknown_model_is_an_error():
    with pytest.raises(KeyError):
        PRICING.price("gpt-9", Usage(1, 1, 0, 0), dt.date(2026, 10, 1))


def test_ledger_round_trip_and_summary(tmp_path):
    led = Ledger(tmp_path / "ledger.jsonl")
    led.append({"profile": "routed", "task_class": "T1", "cost_usd": 0.01, "ok": True})
    led.append({"profile": "routed", "task_class": "T1", "cost_usd": 0.02, "ok": False})
    led.append({"profile": "all-opus", "task_class": "T1", "cost_usd": 0.10, "ok": True})
    rows = summary(led.read())
    routed = [r for r in rows if r["profile"] == "routed"][0]
    assert routed["calls"] == 2 and routed["cost_usd"] == pytest.approx(0.03) and routed["ok"] == 1


def test_claude_cache_writes_priced_at_write_rate():
    u = Usage(input=10_000, output=0, thinking=0, cached=0, cache_write=8_000)
    expected = (2_000 * 4.00 + 8_000 * 5.00) / 1e6
    assert PRICING.price("claude-opus-5-5", u, dt.date(2026, 10, 1)) == pytest.approx(expected)
