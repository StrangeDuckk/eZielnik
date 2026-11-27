"""
Serwis rozpoznawania zdjęć eZielnika (tylko sieć wewnętrzna Dockera, bez domeny).

GET  /health   – stan modeli (API pyta o to przed wysłaniem zdjęcia)
POST /analyze  – multipart: image (plik) + request (JSON z roślinami z bazy i słownikami)
"""

import io
import json
import logging
import threading

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from . import settings
from .service import Recognizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

Image.MAX_IMAGE_PIXELS = 50_000_000   # ochrona przed "bombami" dekompresji

app = FastAPI(title="eZielnik – rozpoznawanie", docs_url=None, redoc_url=None, openapi_url=None)
recognizer = Recognizer()


@app.on_event("startup")
def start_loading() -> None:
    threading.Thread(target=recognizer.load, name="model-loader", daemon=True).start()


@app.get("/health")
def health() -> dict:
    return recognizer.health()


@app.post("/analyze")
def analyze(image: UploadFile = File(...), request: str = Form("{}")) -> dict:
    if recognizer.status != "ready":
        raise HTTPException(503, detail=recognizer.health())

    data = image.file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Zdjęcie jest za duże.")

    try:
        picture = Image.open(io.BytesIO(data))
        picture = ImageOps.exif_transpose(picture).convert("RGB")
        picture.thumbnail((settings.MAX_IMAGE_SIDE, settings.MAX_IMAGE_SIDE))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(400, "Nie udało się odczytać zdjęcia.")

    try:
        payload = json.loads(request or "{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "Nieprawidłowy JSON w polu request.")

    return recognizer.analyze(picture, payload)
