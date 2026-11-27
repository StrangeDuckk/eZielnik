"""
BioCLIP wypełnia formularz wyszukiwania eZielnika.

Dla każdego pola model porównuje zdjęcie z opisami wszystkich dozwolonych
wartości (np. kolory liścia) i wybiera najlepiej pasującą. Pole zostaje
wypełnione tylko wtedy, gdy model jest wystarczająco pewny – w przeciwnym razie
zostaje "Nie wiem", tak jak u użytkownika, który nie jest pewien.

Smak, zapach, grubość, wielkość i miesiąc zbioru nie są widoczne na zdjęciu,
więc nie są wypełniane.
"""

from dataclasses import dataclass, asdict

import numpy as np

from . import form_prompts as fp
from . import settings
from .bioclip import BioClip


@dataclass
class DictItem:
    id: int
    name: str


@dataclass
class FieldGuess:
    part: str          # "plant", "leaf", "flower", "fruit", "hat", "stalk"
    field: str         # "type", "color", "shape", "surface", "hasSpots"
    id: int | None     # wybrana wartość słownika (dla pól Tak/Nie: None)
    value: bool | None # tylko dla pól Tak/Nie
    name: str          # wartość po polsku (do wyświetlenia)
    score: float
    accepted: bool


def _pick(model: BioClip, image_vec, options: list[tuple[DictItem, list[str]]]):
    """Zwraca (najlepsza opcja, pewność) albo (None, 0)."""
    if len(options) < 2:
        return None, 0.0
    vectors = model.class_vectors([prompts for _, prompts in options])
    probs = model.probabilities(image_vec, vectors)
    best = int(np.argmax(probs))
    return options[best][0], float(probs[best])


def fill(model: BioClip, image_vec: np.ndarray, dictionaries: dict) -> dict:
    def items(name: str) -> list[DictItem]:
        return [DictItem(int(d["id"]), str(d["name"])) for d in dictionaries.get(name, [])]

    plant_types = items("plantTypes")
    colors = items("colors")
    shapes = items("shapes")
    surfaces = items("surfaces")

    guesses: list[FieldGuess] = []

    # ---------- 1. typ rośliny ----------
    type_options = [(t, fp.PLANT_TYPES[fp.key(t.name)]) for t in plant_types if fp.key(t.name) in fp.PLANT_TYPES]
    plant_type, type_score = _pick(model, image_vec, type_options)
    type_key = fp.key(plant_type.name) if plant_type else None
    type_ok = plant_type is not None and type_score >= settings.FORM_TYPE_MIN

    if plant_type:
        guesses.append(FieldGuess("plant", "type", plant_type.id, None, plant_type.name,
                                  type_score, type_ok))

    # ---------- 2. które części widać ----------
    organ_names = list(fp.ORGANS)
    organ_probs = model.probabilities(image_vec, model.class_vectors([fp.ORGANS[o] for o in organ_names]))
    organs = {name: float(p) for name, p in zip(organ_names, organ_probs)}

    is_fungus = type_ok and type_key == "grzyb"
    is_tree = type_ok and type_key == "drzewo"

    visible = set()
    if is_fungus:
        visible.add("hat")
    else:
        if organs["flower"] >= settings.FORM_ORGAN_MIN:
            visible.add("flower")
        if organs["fruit"] >= settings.FORM_ORGAN_MIN:
            visible.add("fruit")
        if organs["leaf"] >= settings.FORM_ORGAN_MIN or organs["whole"] >= 2 * settings.FORM_ORGAN_MIN:
            visible.add("leaf")
        if is_tree and organs["bark"] >= settings.FORM_ORGAN_MIN:
            visible.add("stalk")
        if not type_ok and organs["hat"] >= 2 * settings.FORM_ORGAN_MIN:
            visible.add("hat")

    # ---------- 3. kolor / kształt / powierzchnia każdej widocznej części ----------
    def dict_field(part: str, field: str, values: list[DictItem], prompt_for):
        options = []
        for item in values:
            prompts = prompt_for(fp.key(item.name))
            if prompts:
                options.append((item, prompts))
        best, score = _pick(model, image_vec, options)
        if best is not None:
            guesses.append(FieldGuess(part, field, best.id, None, best.name, score,
                                      score >= settings.FORM_FIELD_MIN))

    for part in ("leaf", "flower", "fruit", "hat", "stalk"):
        if part not in visible:
            continue

        allowed_colors = set(fp.COLORS_FOR.get(part, []))
        dict_field(part, "color", colors,
                   lambda k, p=part: [fp.COLOR_TEMPLATES[p].format(fp.COLOR_WORDS[k])]
                   if k in allowed_colors and k in fp.COLOR_WORDS else None)

        if part in fp.SHAPES_FOR:
            shape_prompts = fp.SHAPES_FOR[part]
            dict_field(part, "shape", shapes,
                       lambda k, sp=shape_prompts: [sp[k]] if k in sp else None)

        if part in fp.SURFACES_FOR:
            allowed_surfaces = set(fp.SURFACES_FOR[part])
            dict_field(part, "surface", surfaces,
                       lambda k, p=part, a=allowed_surfaces: [fp.SURFACE_TEMPLATES[p].format(fp.SURFACE_WORDS[k])]
                       if k in a and k in fp.SURFACE_WORDS else None)

    # ---------- 4. pola Tak/Nie ----------
    for (part, field), (yes_prompts, no_prompts) in fp.FLAGS.items():
        if part not in visible:
            continue
        probs = model.probabilities(image_vec, model.class_vectors([yes_prompts, no_prompts]))
        value = bool(probs[0] >= probs[1])
        score = float(max(probs))
        guesses.append(FieldGuess(part, field, None, value, "Tak" if value else "Nie", score,
                                  score >= settings.FORM_FLAG_MIN))

    return {
        "organs": organs,
        "visibleParts": sorted(visible),
        "fields": [asdict(g) for g in guesses],
    }
