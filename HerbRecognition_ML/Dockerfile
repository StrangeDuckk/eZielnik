# =====================================================================
#  HerbRecognition_ML – rozpoznawanie roślin ze zdjęcia (BioCLIP + PlantCLEF)
#  Kontekst budowania: folder HerbRecognition_ML
#  Modele NIE są w obrazie – pobierają się przy pierwszym starcie do wolumenu /models.
# =====================================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ML_MODELS_DIR=/models \
    HF_HOME=/models/hf \
    OMP_NUM_THREADS=2

WORKDIR /srv

# PyTorch w wersji tylko na procesor (serwer nie ma karty graficznej)
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY data ./data

# użytkownik bez uprawnień roota; wolumen z modelami należy do niego
RUN useradd --create-home --uid 10001 ml \
    && mkdir -p /models \
    && chown -R ml /models
USER ml

EXPOSE 8000

# 1) pobranie modeli, jeśli ich nie ma (pierwszy start: kilkanaście minut)
# 2) serwer – modele wczytują się w tle, /health pokazuje postęp
CMD ["sh", "-c", "python -m app.setup_models && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
