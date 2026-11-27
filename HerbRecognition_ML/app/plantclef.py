"""
Model 2: PlantCLEF 2024 od Pl@ntNet (licencja CC BY 4.0).

ViT-B/14 (DINOv2) dotrenowany na ok. 1,4 mln zdjęć 7806 gatunków roślin
naczyniowych z Europy. Klasyczny klasyfikator: zdjęcie -> prawdopodobieństwo
każdego z 7806 gatunków. Nie rozpoznaje grzybów i nie umie odpowiadać na
pytania o cechy – dlatego oddaje tylko głos "ze zdjęcia".

Pliki w PLANTCLEF_DIR (przygotowuje je setup_models.py):
  model.pt             – same wagi (bez stanu optymalizatora), ok. 350 MB
  class_mapping.txt    – numer wyjścia modelu -> numer gatunku
  species_names.csv    – numer gatunku -> nazwa łacińska
"""

import csv
import logging
import re

import numpy as np
import timm
import torch
from PIL import Image
from timm.data import create_transform, resolve_data_config

from . import settings
from .names import display_name

log = logging.getLogger("ml.plantclef")

MODEL_FILE = "model.pt"
MAPPING_FILE = "class_mapping.txt"
NAMES_FILE = "species_names.csv"


def files_ready() -> bool:
    return all((settings.PLANTCLEF_DIR / f).exists() for f in (MODEL_FILE, MAPPING_FILE, NAMES_FILE))


def read_class_mapping(path) -> list[str]:
    """Jedna linia = jedno wyjście modelu; numer gatunku to ostatnia liczba w linii."""
    ids = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = re.split(r"[\s,;]+", line.strip())
        if parts and parts[-1]:
            ids.append(parts[-1])
    return ids


def read_species_names(path) -> dict[str, str]:
    with open(path, encoding="utf-8", newline="") as f:
        return {row["species_id"]: row["species"] for row in csv.DictReader(f)}


class PlantClef:
    def __init__(self):
        folder = settings.PLANTCLEF_DIR
        self.species_ids = read_class_mapping(folder / MAPPING_FILE)
        names = read_species_names(folder / NAMES_FILE)
        # nazwa dla każdego wyjścia modelu (gdy brak w CSV – numer gatunku)
        self.labels = [display_name(names.get(sid, "")) or f"gatunek {sid}" for sid in self.species_ids]

        log.info("Wczytywanie PlantCLEF (%d gatunków) …", len(self.species_ids))

        # dynamic_img_size: wagi są dla 518 px, ale można podać mniejsze zdjęcie (szybciej)
        self.model = timm.create_model(
            settings.PLANTCLEF_ARCH,
            pretrained=False,
            num_classes=len(self.species_ids),
            dynamic_img_size=True)

        # mmap: wagi nie są kopiowane do RAM dwa razy (ważne na serwerze z małą pamięcią)
        state = torch.load(folder / MODEL_FILE, map_location="cpu", weights_only=True, mmap=True)
        self.model.load_state_dict(state)
        del state
        self.model.eval()

        config = resolve_data_config({}, model=self.model)
        size = settings.PLANTCLEF_IMG_SIZE
        config["input_size"] = (3, size, size)
        config["crop_pct"] = 1.0
        self.transform = create_transform(**config, is_training=False)

        log.info("PlantCLEF gotowy (zdjęcie %d px)", size)

    @torch.inference_mode()
    def predict(self, image: Image.Image, top_k: int = settings.TOP_K) -> list[tuple[str, float]]:
        tensor = self.transform(image).unsqueeze(0)
        probs = self.model(tensor).softmax(dim=-1)[0].numpy()
        best = np.argsort(-probs)[:top_k]
        return [(self.labels[i], float(probs[i])) for i in best]

    def all_names(self) -> list[str]:
        return [n for n in self.labels if not n.startswith("gatunek ")]
