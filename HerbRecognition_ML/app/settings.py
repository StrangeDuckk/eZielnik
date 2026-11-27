"""
Ustawienia serwisu rozpoznawania (zmienne środowiskowe z docker-compose).

Wszystkie modele i pliki pomocnicze leżą w ML_MODELS_DIR (trwały wolumen),
więc pobierają się tylko raz – przy pierwszym uruchomieniu.
"""

import os
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "tak")


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


# ----- katalogi -----
MODELS_DIR = Path(os.getenv("ML_MODELS_DIR", "/models"))
CACHE_DIR = MODELS_DIR / "cache"
PLANTCLEF_DIR = MODELS_DIR / "plantclef"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# biblioteka huggingface trzyma pobrane modele w HF_HOME (ustawiane w Dockerfile)

# ----- model 1: BioCLIP -----
# "hf-hub:imageomics/bioclip"   – ViT-B/16, ok. 0,6 GB RAM (domyślny, pasuje do małego serwera)
# "hf-hub:imageomics/bioclip-2" – ViT-L/14, dokładniejszy, ale ok. 1,7 GB RAM
BIOCLIP_MODEL = os.getenv("BIOCLIP_MODEL", "hf-hub:imageomics/bioclip")

# ----- model 2: PlantCLEF 2024 (Pl@ntNet) -----
PLANTCLEF_ENABLED = _bool("PLANTCLEF_ENABLED", True)
PLANTCLEF_ARCH = "vit_base_patch14_reg4_dinov2.lvd142m"
PLANTCLEF_VARIANT = os.getenv(
    "PLANTCLEF_VARIANT", "vit_base_patch14_reg4_dinov2_lvd142m_pc24_onlyclassifier_then_all")
# 518 = rozdzielczość, w której model był trenowany; 392 jest ok. 2x szybsze, minimalnie mniej dokładne
PLANTCLEF_IMG_SIZE = _int("PLANTCLEF_IMG_SIZE", 518)

PLANTCLEF_ZENODO_URL = os.getenv(
    "PLANTCLEF_ZENODO_URL",
    "https://zenodo.org/records/10848263/files/"
    "PlantNet_PlantCLEF2024_pretrained_models_on_the_flora_of_south-western_europe.tar?download=1")

# suma kontrolna archiwum podana na Zenodo – sprawdzamy, czy pobrało się w całości
PLANTCLEF_ZENODO_MD5 = os.getenv("PLANTCLEF_ZENODO_MD5", "42bc1bf3725ebe0bc93a2167c6b3deda")

# metadane zbioru treningowego – potrzebne tylko po to, żeby zamienić numer gatunku na nazwę łacińską
PLANTCLEF_CSV_URL = os.getenv(
    "PLANTCLEF_CSV_URL",
    "https://lab.plantnet.org/LifeCLEF/PlantCLEF2024/single_plant_training_data/"
    "PlantCLEF2024singleplanttrainingdata.csv")

# ----- działanie -----
TORCH_THREADS = _int("TORCH_THREADS", 2)
TOP_K = 5
MAX_IMAGE_SIDE = 1024
MAX_UPLOAD_BYTES = 12 * 1024 * 1024

# ----- wypełnianie formularza (progi pewności 0–1; niżej = więcej pól, ale więcej pomyłek) -----
FORM_TYPE_MIN = _float("FORM_TYPE_MIN", 0.50)     # typ rośliny
FORM_ORGAN_MIN = _float("FORM_ORGAN_MIN", 0.15)   # czy dana część jest widoczna na zdjęciu
FORM_FIELD_MIN = _float("FORM_FIELD_MIN", 0.40)   # kolor / kształt / powierzchnia
FORM_FLAG_MIN = _float("FORM_FLAG_MIN", 0.75)     # pola Tak/Nie
