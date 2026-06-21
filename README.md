# Port Dues Calculator

Reads a **port tariff PDF** plus a **vessel profile** and calculates the port dues payable for
a vessel's call — **Light, Port, Towage, VTS, Pilotage and Running-of-lines (Berthing) dues**.

The tariff rules are **discovered from the PDF by an LLM (Gemini), not hardcoded**. To support a
different port or a new edition of the tariff book, you point the extractor at the new PDF and
re-run — no code changes.

## Result (vessel `SUDESTADA`, Port of Durban)

Rules auto-extracted from the *Transnet National Ports Authority Tariff Book 2024–25* by Gemini,
then applied by the calculator:

| Due | Tariff § | Calculated (ZAR) | Ground truth | Diff |
|---|---|---:|---:|---:|
| Light Dues | 1.1.1 | 60,062.04 | 60,062.04 | 0.00% |
| Port Dues | 4.1.1 | 199,371.35 | 199,549.22 | −0.09% |
| Towage Dues | 3.6 | 147,074.38 | 147,074.38 | 0.00% |
| VTS Dues | 2.1.1 | 33,345.00 | 33,315.75 | +0.09% |
| Pilotage Dues | 3.3 | 47,189.94 | 47,189.94 | 0.00% |
| Running of Vessel Lines (Berthing) | 3.8 | 19,639.50 | 19,639.50 | 0.00% |
| **Total** | | **506,682.21** | **506,830.83** | **−0.03%** |

Four of six match to the cent; the other two are within 0.1% (see *Notes on accuracy*).

## How it works

Two layers, deliberately separated:

```
  Tariff PDF ──► [1] extract_rules.py ──►  rules/<port>_tariff.json  ──► [2] calculator.py ──► dues
   (any port)     (Gemini reads the PDF      (structured, human-          (generic maths,
                   and writes the rules)      readable rules)              port-agnostic)
```

1. **`src/extract_rules.py` — the "find the logic" layer.** Sends the tariff text to Gemini and
   asks it to express each due as a structured rule (which tonnage basis, rate, bands, minimum,
   and whether it's charged once or for both entry + departure). It is given the *general grammar*
   of how port tariffs are shaped — never the specific numbers. Those come out of the PDF.
2. **`src/calculator.py` — the "apply the logic" layer.** A small, deterministic interpreter for
   those rules. It knows nothing about Durban or any rate; give it another port's rules and it
   computes that port's dues. This is why the maths is exact and auditable.

The extracted `rules/durban_tariff.json` is committed so the calculator runs **without an API key**.
It is a cache of Gemini's output, regenerable at any time.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then paste your free Gemini key from https://aistudio.google.com/apikey
```

## Run

Calculate dues for the sample vessel and check against the published ground truth:

```bash
python -m src.main vessels/sudestada.json --validate
```

Re-extract the rules from the PDF with Gemini (proves nothing is hardcoded):

```bash
python -m src.extract_rules --pdf data/port_tariff.pdf --port Durban
```

Generalise to another port/document — same code, new inputs:

```bash
python -m src.extract_rules --pdf data/<other_port>.pdf --port "Cape Town"
python -m src.main vessels/<your_vessel>.json --rules rules/cape_town_tariff.json
```

## The one pattern that unlocks the whole tariff

Almost every due is **"per 100 tons (or part thereof) of Gross Tonnage × a rate"**, often **× 2**
because pilotage, towage and berthing are charged once for entering and once for leaving. Some add
a fixed basic fee (Pilotage, Berthing), one is banded by tonnage (Towage), and Port Dues adds a
per-day component. Five calculation shapes cover all six dues — and likely most similar tariffs.

## Notes on accuracy & a domain judgement call

- **Port Dues (−0.09%)**: exact if the in-port period is 3.396 days; the vessel profile rounds
  `days_alongside` to 3.39. A rounding artefact, not a formula error.
- **VTS (+0.09%)**: `0.65 × GT` = 33,345 vs a published 33,315.75 (R29 difference) — consistent
  with the brief labelling the figures "approximate".
- **"Running of Vessel Lines" is a domain trap.** The document has a section literally titled
  *Running of Vessel Lines* (§3.9) — but the ground-truth figure comes from **Berthing Services
  (§3.8)**, which is what's actually billed for running a vessel's mooring lines at berthing and
  unberthing. The first automated extraction took §3.9 literally and was wrong; recognising that
  "running lines" = berthing service (and that Durban uses the *Other Ports* column, as it isn't
  named in that table) is exactly the kind of human-in-the-loop judgement this design supports.

## Project layout

```
data/                 source PDFs (tariff + task brief)
vessels/sudestada.json  the vessel profile
rules/durban_tariff.json  rules extracted from the PDF by Gemini (the calculator's input)
src/pdf_text.py       PDF -> text
src/extract_rules.py  text -> structured rules (Gemini)
src/calculator.py     rules + vessel -> dues  (generic, deterministic)
src/main.py           CLI
```

## Limitations / next steps

- Covers the six headline dues for a standard cargo call; exemptions, surcharges (e.g. out-of-hours)
  and reductions are out of scope but fit the same rule schema.
- A reviewer step (approve the LLM-extracted rules before they drive billing) is the natural
  production pattern — the JSON is intentionally human-readable for exactly that.
- Easy bonus: wrap `src/main` logic behind a small HTTP API.
