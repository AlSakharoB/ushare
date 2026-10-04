import importlib
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

pipeline: Any = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global pipeline
    model_root = Path(os.environ.get("OCR_MODELS_PATH", "/models"))
    det = model_root / "PP-OCRv5_server_det"
    rec = model_root / "cyrillic_PP-OCRv5_mobile_rec"
    # No runtime model download. Setup must supply explicit local model directories.
    if det.is_dir() and rec.is_dir():
        paddle = importlib.import_module("paddleocr")
        pipeline = paddle.PaddleOCR(
            text_detection_model_name=det.name,
            text_detection_model_dir=str(det),
            text_recognition_model_name=rec.name,
            text_recognition_model_dir=str(rec),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device="cpu",
        )
    yield
    pipeline = None


app = FastAPI(title="ReceiptSplit OCR", lifespan=lifespan)


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> Any:
    if pipeline is None:
        return JSONResponse({"status": "models_unavailable"}, status_code=503)
    return {"status": "ready"}
