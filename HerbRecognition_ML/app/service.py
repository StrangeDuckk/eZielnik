"""
Ładowanie modeli i analiza jednego zdjęcia.

Wynik /analyze zawiera trzy rzeczy, z których API eZielnika robi trzy głosy:
  1. bioclip.candidates   – BioCLIP rozpoznaje gatunek ze zdjęcia,
  2. form                 – BioCLIP wypełnia formularz (API samo uruchamia wyszukiwanie),
  3. plantclef.candidates – PlantCLEF rozpoznaje gatunek ze zdjęcia.
Głosowanie odbywa się w API, bo tylko ono zna bazę roślin.
"""

import logging
import threading
import time

import numpy as np
import torch
from PIL import Image

from . import names, plantclef, settings
from .bioclip import BioClip, species_prompt
from .form_filler import fill

log = logging.getLogger("ml.service")


class Recognizer:
    def __init__(self):
        self.bioclip: BioClip | None = None
        self.plantclef: plantclef.PlantClef | None = None

        # etykiety do rozpoznawania gatunku przez BioCLIP (bez roślin z bazy – te dochodzą w zapytaniu)
        self.static_labels: list[str] = []
        self.static_keys: set[str] = set()
        self.static_vectors: np.ndarray | None = None

        self.status = "starting"
        self.progress = ""
        self.errors: list[str] = []
        self.lock = threading.Lock()   # jedno zdjęcie naraz – serwer ma 2 rdzenie

    # ------------------------------------------------------------------
    #  Start (w tle – serwer HTTP odpowiada na /health od razu)
    # ------------------------------------------------------------------

    def load(self) -> None:
        try:
            torch.set_num_threads(settings.TORCH_THREADS)
            names.load_synonyms(settings.DATA_DIR / "synonyms.txt")

            self.status = "loading"
            self.progress = "BioCLIP"
            self.bioclip = BioClip()

            if settings.PLANTCLEF_ENABLED:
                if plantclef.files_ready():
                    self.progress = "PlantCLEF"
                    try:
                        self.plantclef = plantclef.PlantClef()
                    except Exception as ex:
                        log.exception("PlantCLEF się nie wczytał")
                        self.errors.append(f"PlantCLEF: {ex}")
                else:
                    self.errors.append("PlantCLEF: brak plików modelu (zobacz log setup_models)")

            self._prepare_static_labels()
            self.status = "ready"
            self.progress = ""
            log.info("Serwis gotowy. Etykiet gatunków: %d", len(self.static_labels))
        except Exception as ex:
            log.exception("Nie udało się uruchomić modeli")
            self.status = "error"
            self.errors.append(str(ex))

    def _prepare_static_labels(self) -> None:
        """Nazwy gatunków spoza bazy: cała lista PlantCLEF + grzyby z data/fungi.txt."""
        labels: dict[str, str] = {}

        if self.plantclef:
            for name in self.plantclef.all_names():
                labels.setdefault(names.canonical(name), name)

        fungi = settings.DATA_DIR / "fungi.txt"
        if fungi.exists():
            for line in fungi.read_text(encoding="utf-8").splitlines():
                line = line.split("#", 1)[0].strip()
                if line:
                    shown = names.display_name(line)
                    labels.setdefault(names.canonical(shown), shown)

        self.static_labels = list(labels.values())
        self.static_keys = set(labels.keys())

        def report(done, total):
            self.progress = f"opisy gatunków {done}/{total} (tylko przy pierwszym uruchomieniu)"

        prompts = [species_prompt(n) for n in self.static_labels]
        self.static_vectors = self.bioclip.text_vectors(prompts, progress=report)

    def health(self) -> dict:
        return {
            "status": self.status,
            "progress": self.progress,
            "bioclip": self.bioclip.name if self.bioclip else None,
            "plantclef": self.plantclef is not None,
            "speciesLabels": len(self.static_labels),
            "errors": self.errors,
        }

    # ------------------------------------------------------------------
    #  Analiza zdjęcia
    # ------------------------------------------------------------------

    def analyze(self, image: Image.Image, request: dict) -> dict:
        db_plants = request.get("dbPlants", [])
        dictionaries = request.get("dictionaries", {})

        # klucz nazwy łacińskiej -> id rośliny w bazie
        # (w bazie bywa sam rodzaj, np. "matricaria" – wtedy pasuje każdy gatunek tego rodzaju)
        db_index = DbIndex()
        for plant in db_plants:
            db_index.add(plant.get("latin"), int(plant["id"]))

        timings = {}
        with self.lock:
            # ---------- PlantCLEF ----------
            plantclef_result = None
            if self.plantclef:
                t = time.perf_counter()
                top = self.plantclef.predict(image)
                timings["plantclef"] = _ms(t)
                plantclef_result = {
                    "model": "PlantCLEF 2024 (Pl@ntNet)",
                    "candidates": [_candidate(n, p, db_index) for n, p in top],
                }

            # ---------- BioCLIP: zdjęcie -> gatunek ----------
            t = time.perf_counter()
            image_vec = self.bioclip.encode_image(image)
            timings["bioclipImage"] = _ms(t)

            t = time.perf_counter()
            extra = [names.display_name(p.get("latin")) for p in db_plants if p.get("latin")]
            if plantclef_result:
                extra += [c["latin"] for c in plantclef_result["candidates"]]

            extra = list(dict.fromkeys(n for n in extra if n and names.canonical(n) not in self.static_keys))

            labels = self.static_labels + extra
            vectors = self.static_vectors
            if extra:
                extra_vectors = self.bioclip.text_vectors([species_prompt(n) for n in extra])
                vectors = extra_vectors if vectors is None or len(vectors) == 0 else np.vstack([vectors, extra_vectors])

            probs = self.bioclip.probabilities(image_vec, vectors)
            best = np.argsort(-probs)[:settings.TOP_K]
            bioclip_candidates = [_candidate(labels[i], float(probs[i]), db_index) for i in best]
            timings["bioclipSpecies"] = _ms(t)

            # ---------- BioCLIP: zdjęcie -> formularz ----------
            t = time.perf_counter()
            form = fill(self.bioclip, image_vec, dictionaries)
            timings["bioclipForm"] = _ms(t)

        return {
            "bioclip": {"model": self.bioclip.name, "candidates": bioclip_candidates},
            "plantclef": plantclef_result,
            "form": form,
            "timingsMs": timings,
        }


class DbIndex:
    """Nazwy łacińskie roślin z bazy: pełne (rodzaj + gatunek) i same rodzaje."""

    def __init__(self):
        self.species: dict[str, int] = {}
        self.genera: dict[str, int] = {}

    def add(self, latin: str | None, plant_id: int) -> None:
        key = names.canonical(latin)
        if not key:
            return
        if " " in key:
            self.species.setdefault(key, plant_id)
        else:
            self.genera.setdefault(key, plant_id)

    def find(self, key: str) -> int | None:
        if key in self.species:
            return self.species[key]
        return self.genera.get(key.split(" ")[0]) if key else None


def _candidate(latin: str, score: float, db_index: DbIndex) -> dict:
    key = names.canonical(latin)
    return {
        "latin": names.display_name(latin),
        "key": key,
        "score": round(score, 4),
        "dbId": db_index.find(key),
    }


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
