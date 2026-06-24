"""
LLM rule extraction — the "agent finds the logic" layer.

Reads a port tariff PDF and asks Gemini to express each due as a structured rule
that src/calculator.py can execute. NO rates are hardcoded here: everything the
calculator needs is pulled out of the PDF text by the model.

To target a different port or a new edition of the document, just point this at the
new PDF and re-run — no code changes:

    python -m src.extract_rules --pdf data/port_tariff.pdf --port Durban
"""
import argparse
import json
import os
import time

from dotenv import load_dotenv
from google import genai

from src.pdf_text import full_text

load_dotenv()

# The vocabulary of calculation shapes our calculator understands. This is general
# tariff knowledge (how port dues are typically structured), NOT port-specific data.
METHOD_GUIDE = """
Each due must use exactly ONE of these calculation `method`s:

- "per_100t": amount = ceil(GT/100) * rate
    fields: rate
- "per_100t_plus_period": amount = ceil(GT/100) * (basic_rate + period_rate * days_in_port)
    fields: basic_rate, period_rate
- "banded_per_100t": choose the tonnage band containing GT, then
    amount = band.base + ceil((GT - band.increment_floor)/100) * band.increment
    fields: bands = [ {min, max, base, increment_floor, increment}, ... ]  (max=null for the open top band)
- "per_gt": amount = GT * rate
    fields: rate
- "basic_plus_per_100t": amount = basic_fee + ceil(GT/100) * rate
    fields: basic_fee, rate

Optional on any rule:
- "movements": integer multiplier. Use 2 for services charged once for ENTERING and once for
  LEAVING the port (pilotage, towage, berthing/running-of-lines). Use 1 otherwise.
- "minimum": minimum charge floor, if the tariff states one.
"""

PROMPT = """You are extracting port-dues calculation rules from an official port tariff document.

PORT OF INTEREST: {port}

Extract a rule for EACH of these dues (use the column/rates specific to the port of interest):
1. Light Dues
2. Port Dues
3. Towage Dues  (a.k.a. Tugs / Vessel Assistance)
4. VTS Dues  (Vessel Traffic Services)
5. Pilotage Dues
6. Running of Vessel Lines  -> IMPORTANT: bill this from the BERTHING SERVICES tariff, which
   covers running/handling a vessel's mooring lines for berthing and unberthing. Do NOT use any
   section literally titled "Running of Vessel Lines" if it is a narrow launch/mooring-boat service;
   the conventional "running lines" charge for a port call is the berthing service (entering + leaving).

"Per 100 tons or part thereof" means round the unit count UP (ceiling). Tonnage means GROSS tonnage.

COLUMN SELECTION: tariff tables often have one column per major port plus a general "Other Ports"
column. If the PORT OF INTEREST has its own named column, use it. If it is NOT named in a table,
use the "Other Ports" (general) column for that table.

{method_guide}

Return ONLY a JSON object of this exact shape:
{{
  "port": "{port}",
  "source_document": "<title/edition of the document>",
  "currency": "<currency code, e.g. ZAR>",
  "rules": [
    {{
      "name": "Light Dues",
      "tariff_section": "<section number in the document>",
      "method": "<one of the methods>",
      "... method fields ...": "...",
      "movements": 1,
      "minimum": null,
      "notes": "<short human explanation of the rule and which column you used>"
    }}
    // ... one object per due, in the order listed above
  ]
}}

TARIFF DOCUMENT TEXT:
{document}
"""


def extract(pdf_path, port, retries=4):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    document = full_text(pdf_path)
    prompt = PROMPT.format(port=port, method_guide=METHOD_GUIDE, document=document)
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={"response_mime_type": "application/json", "temperature": 0},
            )
            return json.loads(resp.text)
        except Exception as e:
            transient = any(c in str(e) for c in ("503", "UNAVAILABLE", "429", "500"))
            if transient and attempt < retries - 1:
                time.sleep(2 ** attempt)  # back off: 1s, 2s, 4s
                continue
            raise


def main():
    ap = argparse.ArgumentParser(description="Extract tariff rules from a PDF via Gemini.")
    ap.add_argument("--pdf", default="data/port_tariff.pdf")
    ap.add_argument("--port", default="Durban")
    ap.add_argument("--out", default=None, help="output path (default rules/<port>_tariff.json)")
    args = ap.parse_args()

    out = args.out or f"rules/{args.port.lower().replace(' ', '_')}_tariff.json"
    print(f"Reading {args.pdf} and extracting rules for {args.port} via Gemini ...")
    doc = extract(args.pdf, args.port)
    with open(out, "w") as f:
        json.dump(doc, f, indent=2)
    print(f"Wrote {len(doc.get('rules', []))} rules -> {out}")


if __name__ == "__main__":
    main()
