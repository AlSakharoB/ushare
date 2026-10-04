import json
from pathlib import Path

from receiptsplit.api.app import app

target = Path(__file__).resolve().parents[1] / "artifacts/openapi.json"
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(app.openapi(), ensure_ascii=False), encoding="utf-8")
