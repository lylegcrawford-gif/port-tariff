"""
HTTP API for the port dues calculator (the brief's bonus).

Run it:
    uvicorn src.api:app --reload
Then open http://127.0.0.1:8000/docs for an interactive form, or POST JSON:

    curl -X POST http://127.0.0.1:8000/calculate \
         -H "Content-Type: application/json" \
         -d @vessels/sudestada.json

It exposes exactly the same engine as the CLI: a vessel profile in, an itemised
set of port dues out. The `port` field on the vessel selects which extracted
rule set to apply (defaults to Durban).
"""
import glob
import json
import os

from fastapi import Body, FastAPI, HTTPException

from src.calculator import compute_all

RULES_DIR = os.path.join(os.path.dirname(__file__), "..", "rules")

app = FastAPI(
    title="Port Dues API",
    description="Calculate port dues for a vessel from tariff rules extracted from a port's PDF.",
    version="1.0",
)


def _slug(port):
    return port.lower().replace(" / ", "_").replace(" ", "_")


def _load_rules(port):
    path = os.path.join(RULES_DIR, f"{_slug(port)}.json")
    if not os.path.exists(path):
        available = [os.path.basename(p)[:-5] for p in glob.glob(os.path.join(RULES_DIR, "*.json"))]
        raise HTTPException(status_code=404,
                            detail=f"No rules for port '{port}'. Available: {sorted(available)}")
    with open(path) as f:
        return json.load(f)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ports")
def ports():
    """List the ports we have extracted rules for."""
    files = glob.glob(os.path.join(RULES_DIR, "*.json"))
    return {"ports": sorted(json.load(open(f)).get("port", os.path.basename(f)[:-5]) for f in files)}


@app.post("/calculate")
def calculate(vessel: dict = Body(..., description="Vessel profile JSON (as in the task brief)")):
    """Calculate all applicable port dues for a vessel.

    The vessel's `port` field selects the tariff (defaults to Durban).
    Returns an itemised breakdown plus the total in the tariff currency.
    """
    if "technical_specs" not in vessel or "gross_tonnage" not in vessel.get("technical_specs", {}):
        raise HTTPException(status_code=422, detail="vessel.technical_specs.gross_tonnage is required")

    port = vessel.get("port", "Durban")
    rules_doc = _load_rules(port)
    result = compute_all(rules_doc["rules"], vessel)

    return {
        "vessel": vessel.get("vessel_metadata", {}).get("name"),
        "port": port,
        "currency": rules_doc.get("currency", "ZAR"),
        "source_document": rules_doc.get("source_document"),
        "items": result["items"],
        "total": result["total_zar"],
    }
