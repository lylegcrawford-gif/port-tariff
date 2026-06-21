"""
Port-dues calculator CLI.

  python -m src.main vessels/sudestada.json
  python -m src.main vessels/sudestada.json --rules rules/durban_tariff.json --validate

It loads a vessel profile + a set of tariff rules (extracted from the port's PDF),
computes every applicable due, and prints an itemised breakdown.
"""
import argparse
import json

from src.calculator import compute_all

# Published ground-truth values for the SUDESTADA @ Durban (from the task brief).
# Keyed by a lowercase keyword so validation tolerates however the LLM labels each due.
GROUND_TRUTH = {
    "light": 60062.04,
    "port": 199549.22,
    "towage": 147074.38,
    "vts": 33315.75,
    "pilotage": 47189.94,
    "running": 19639.50,
}


def match_ground_truth(due_name):
    name = due_name.lower()
    for key, value in GROUND_TRUTH.items():
        if key in name:
            return value
    return None


def load(path):
    with open(path) as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description="Calculate port dues for a vessel.")
    ap.add_argument("vessel", help="path to vessel profile JSON")
    ap.add_argument("--rules", default="rules/durban_tariff.json",
                    help="path to extracted tariff rules JSON")
    ap.add_argument("--validate", action="store_true",
                    help="compare results against the published ground truth")
    args = ap.parse_args()

    vessel = load(args.vessel)
    rules_doc = load(args.rules)
    result = compute_all(rules_doc["rules"], vessel)

    name = vessel["vessel_metadata"]["name"]
    port = vessel.get("port", rules_doc.get("port", "?"))
    print(f"\nPort dues for {name} @ {port}")
    print(f"Source: {rules_doc.get('source_document', '?')}")
    print("=" * 78)

    if args.validate:
        print(f"{'Due':<46}{'Calculated':>12}{'Target':>12}{'Diff%':>8}")
    else:
        print(f"{'Due':<58}{'Amount (ZAR)':>20}")
    print("-" * 78)

    for item in result["items"]:
        due, amt = item["due"], item["amount_zar"]
        if args.validate:
            tgt = match_ground_truth(due)
            if tgt:
                diff = 100 * (amt - tgt) / tgt
                print(f"{due:<46}{amt:>12,.2f}{tgt:>12,.2f}{diff:>7.2f}%")
            else:
                print(f"{due:<46}{amt:>12,.2f}{'-':>12}{'-':>8}")
        else:
            print(f"{due:<58}{amt:>20,.2f}")

    print("-" * 78)
    print(f"{'TOTAL':<58}{result['total_zar']:>20,.2f}")

    if args.validate:
        gt_total = round(sum(GROUND_TRUTH.values()), 2)
        diff = 100 * (result["total_zar"] - gt_total) / gt_total
        print(f"{'GROUND-TRUTH TOTAL':<58}{gt_total:>20,.2f}")
        print(f"{'TOTAL DIFFERENCE':<58}{diff:>19.2f}%")


if __name__ == "__main__":
    main()
