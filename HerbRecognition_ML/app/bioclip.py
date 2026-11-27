"""
Model 1: BioCLIP (Imageomics, licencja MIT).

Model zamienia zdjęcie i tekst na wektory w tej samej przestrzeni. Im bliżej
wektor zdjęcia jest wektora opisu (np. "a photo of Mentha piperita."), tym
lepiej opis pasuje do zdjęcia. Dzięki temu ten sam model:
  - rozpoznaje gatunek (opisy = nazwy łacińskie),
  - wypełnia formularz (opisy = cechy, np. "a plant with heart-shaped leaves").

Wektory opisów liczą się raz i są zapisywane na dysku (cache), bo nazw
gatunków jest kilka tysięcy.
"""

import hashlib
import logging
import threading

import numpy as np
import open_clip
import torch
from PIL import Image

from . import settings

log = logging.getLogger("ml.bioclip")


class TextCache:
    """Wektory tekstów zapisane w pliku .npz – liczone tylko raz."""

    def __init__(self, model_name: str):
        tag = hashlib.sha1(model_name.encode()).hexdigest()[:10]
        self.path = settings.CACHE_DIR / f"text_{tag}.npz"
        self.items: dict[str, np.ndarray] = {}
        self.dirty = False
        self.lock = threading.Lock()

        if self.path.exists():
            try:
                data = np.load(self.path, allow_pickle=False)
                for text, vec in zip(data["texts"], data["vectors"]):
                    self.items[str(text)] = vec
                log.info("Wczytano %d wektorów tekstu z %s", len(self.items), self.path)
            except Exception:   # uszkodzony plik – policzymy od nowa
                log.exception("Nie udało się wczytać %s", self.path)

    def save(self) -> None:
        with self.lock:
            if not self.dirty or not self.items:
                return
            settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            texts = np.array(list(self.items.keys()))
            vectors = np.stack(list(self.items.values())).astype(np.float32)
            tmp = self.path.with_name(self.path.stem + ".tmp.npz")
            np.savez(tmp, texts=texts, vectors=vectors)
            tmp.replace(self.path)
            self.dirty = False


class BioClip:
    def __init__(self, model_name: str = settings.BIOCLIP_MODEL):
        log.info("Wczytywanie %s …", model_name)
        self.name = model_name
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(model_name)
        self.tokenizer = open_clip.get_tokenizer(model_name)
        self.model.eval()
        self.logit_scale = float(self.model.logit_scale.exp().item())
        self.cache = TextCache(model_name)
        log.info("BioCLIP gotowy (logit_scale=%.1f)", self.logit_scale)

    # ------------------------------------------------------------------

    @torch.inference_mode()
    def encode_image(self, image: Image.Image) -> np.ndarray:
        tensor = self.preprocess(image).unsqueeze(0)
        vec = self.model.encode_image(tensor)
        vec = vec / vec.norm(dim=-1, keepdim=True)
        return vec[0].float().numpy()

    @torch.inference_mode()
    def _encode_texts(self, texts: list[str]) -> np.ndarray:
        tokens = self.tokenizer(texts)
        vec = self.model.encode_text(tokens)
        vec = vec / vec.norm(dim=-1, keepdim=True)
        return vec.float().numpy()

    def text_vectors(self, texts: list[str], batch: int = 64, progress=None) -> np.ndarray:
        """Wektory dla listy tekstów (z cache; brakujące są liczone i dopisywane)."""
        missing = [t for t in dict.fromkeys(texts) if t not in self.cache.items]

        for start in range(0, len(missing), batch):
            chunk = missing[start:start + batch]
            vectors = self._encode_texts(chunk)
            with self.cache.lock:
                for text, vec in zip(chunk, vectors):
                    self.cache.items[text] = vec
                self.cache.dirty = True
            if progress:
                progress(min(start + batch, len(missing)), len(missing))

        if missing:
            self.cache.save()

        if not texts:
            return np.zeros((0, 1), dtype=np.float32)
        return np.stack([self.cache.items[t] for t in texts])

    def probabilities(self, image_vec: np.ndarray, text_vecs: np.ndarray) -> np.ndarray:
        """Softmax podobieństw zdjęcia do opisów – wynik sumuje się do 1."""
        if len(text_vecs) == 0:
            return np.zeros(0, dtype=np.float32)
        logits = self.logit_scale * (text_vecs @ image_vec)
        logits -= logits.max()
        exp = np.exp(logits)
        return exp / exp.sum()

    def class_vectors(self, prompts_per_class: list[list[str]]) -> np.ndarray:
        """Jeden wektor na klasę = uśredniony wektor kilku opisów tej klasy."""
        flat = [p for prompts in prompts_per_class for p in prompts]
        vectors = self.text_vectors(flat)

        out, i = [], 0
        for prompts in prompts_per_class:
            mean = vectors[i:i + len(prompts)].mean(axis=0)
            out.append(mean / np.linalg.norm(mean))
            i += len(prompts)
        return np.stack(out)


def species_prompt(latin: str) -> str:
    return f"a photo of {latin}."
