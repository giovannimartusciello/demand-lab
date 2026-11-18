"""Regenerate the published baseline dataset using only the standard library."""
import csv
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from models import generate_demand
with (ROOT/"data/catalog.json").open(encoding="utf-8") as handle:
    catalog=json.load(handle)
with (ROOT/"data/demand.csv").open("w",newline="",encoding="utf-8") as handle:
    writer=csv.writer(handle)
    writer.writerow(["date","item_id","demand"])
    for item in catalog:
        for t,value in enumerate(generate_demand(item)):
            writer.writerow([f"{2021+t//12}-{t%12+1:02d}-01",item["id"],value])
print("Wrote 240 deterministic monthly observations.")
