"""
Generic tariff calculator.

This module knows NOTHING about Durban or any specific rate. It only knows how to
APPLY a structured tariff rule (extracted from a PDF by the LLM) to a vessel.
Swap in a different port's rules and the same code computes that port's dues.

A "rule" is a small dict with a `method` and the parameters that method needs:

  per_100t              amount = ceil(GT/100) * rate
  per_100t_plus_period  amount = ceil(GT/100) * (basic_rate + period_rate * days_in_port)
  banded_per_100t       pick the tonnage band, then base + ceil((GT-floor)/100) * increment
  per_gt                amount = GT * rate
  basic_plus_per_100t   amount = basic_fee + ceil(GT/100) * rate

Optional modifiers on any rule:
  movements   multiply the result (e.g. 2 = vessel entering + leaving)   default 1
  minimum     floor the result at this value                              default none
"""
import math


def per_100t(tons):
    """'Per 100 tons or part thereof' -> always round the unit count UP."""
    return math.ceil(tons / 100)


def _pick_band(bands, gt):
    """Return the band whose [min, max] range contains the vessel's GT."""
    for b in bands:
        lo = b.get("min", 0)
        hi = b.get("max")  # null/None means open-ended top band
        if gt >= lo and (hi is None or gt <= hi):
            return b
    raise ValueError(f"No tonnage band matches GT={gt}")


def compute_due(rule, vessel):
    """Apply one tariff rule to one vessel and return the amount in ZAR."""
    specs = vessel["technical_specs"]
    ops = vessel.get("operational_data", {})
    gt = specs["gross_tonnage"]
    days = ops.get("days_alongside", 0) or 0

    method = rule["method"]

    if method == "per_100t":
        amount = per_100t(gt) * rule["rate"]

    elif method == "per_100t_plus_period":
        amount = per_100t(gt) * (rule["basic_rate"] + rule["period_rate"] * days)

    elif method == "banded_per_100t":
        band = _pick_band(rule["bands"], gt)
        floor = band.get("increment_floor", band.get("min", 0))
        above = max(0, gt - floor)
        amount = band["base"] + per_100t(above) * band.get("increment", 0)

    elif method == "per_gt":
        amount = gt * rule["rate"]

    elif method == "basic_plus_per_100t":
        amount = rule["basic_fee"] + per_100t(gt) * rule["rate"]

    else:
        raise ValueError(f"Unknown tariff method: {method}")

    amount *= rule.get("movements", 1)

    minimum = rule.get("minimum")
    if minimum is not None:
        amount = max(amount, minimum)

    return round(amount, 2)


def compute_all(rules, vessel):
    """Run every rule and return an itemised breakdown plus the total."""
    items = []
    for rule in rules:
        amount = compute_due(rule, vessel)
        items.append({
            "due": rule["name"],
            "tariff_section": rule.get("tariff_section"),
            "amount_zar": amount,
            "basis": rule.get("notes", ""),
        })
    total = round(sum(i["amount_zar"] for i in items), 2)
    return {"items": items, "total_zar": total}
