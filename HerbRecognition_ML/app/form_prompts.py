"""
Opisy po angielsku dla wartości słowników eZielnika (BioCLIP rozumie tylko angielski).

Klucze to polskie nazwy ze słowników w bazie zapisane bez polskich znaków
i małymi literami (funkcja key). Jeśli admin doda nową wartość słownika,
której tu nie ma, model ją pominie – wystarczy dopisać ją do właściwego słownika.

Dla każdej części rośliny są tylko wartości, które mają sens (np. liść nie
bywa "lejowaty", a kapelusz "pierzasty").
"""

import unicodedata


def key(name: str) -> str:
    text = name.replace("ł", "l").replace("Ł", "L")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().replace(",", " ").replace("(", " ").replace(")", " ").split())


# ---------------------------------------------------------------------
#  Typ rośliny
# ---------------------------------------------------------------------

# kwiaty z bliska (np. rumianek) też muszą trafiać do "zioło", a nie do "grzyb" –
# stąd kilka opisów kwiatów i liści w klasie zioła
PLANT_TYPES = {
    "drzewo": ["a photo of a tall tree.", "a photo of a tree trunk with bark.",
               "a photo of a forest tree with a crown of branches."],
    "ziolo": ["a photo of a herbaceous plant.", "a photo of a wildflower.", "a photo of a small green plant.",
              "a close-up photo of a flower with petals.", "a photo of a flowering plant in a meadow.",
              "a close-up photo of the leaves of a small plant."],
    "grzyb": ["a photo of a mushroom.", "a photo of a fungus.", "a photo of a toadstool growing on the forest floor.",
              "a photo of a bracket fungus on a tree trunk."],
}

# ---------------------------------------------------------------------
#  Które części widać na zdjęciu
# ---------------------------------------------------------------------

ORGANS = {
    "flower": ["a close-up photo of a flower.", "a photo of blooming flowers."],
    "leaf": ["a close-up photo of leaves.", "a photo of green foliage."],
    "fruit": ["a photo of fruits or berries on a plant.", "a close-up photo of a fruit."],
    "hat": ["a photo of a mushroom cap.", "a photo of a mushroom growing on the ground."],
    "bark": ["a photo of tree bark.", "a close-up photo of a tree trunk."],
    "whole": ["a photo of a whole plant.", "a photo of a whole tree."],
}

# ---------------------------------------------------------------------
#  Kolory: klucz -> angielska nazwa koloru
# ---------------------------------------------------------------------

COLOR_WORDS = {
    "bialy": "white",
    "kremowy": "cream",
    "zolty": "yellow",
    "zloty": "golden yellow",
    "pomaranczowy": "orange",
    "czerwony": "red",
    "burgundowy": "burgundy",
    "ciemny czerwony": "dark red",
    "brazowy": "brown",
    "ciemny brazowy": "dark brown",
    "bezowy": "beige",
    "rozowy": "pink",
    "rozany": "magenta pink",
    "purpurowy": "purple",
    "fioletowy": "violet",
    "niebieski": "blue",
    "ciemny niebieski": "dark blue",
    "jasny niebieski": "light blue",
    "turkusowy": "turquoise",
    "jasny zielony": "light green",
    "zielony": "green",
    "ciemny zielony": "dark green",
    "oliwkowy": "olive green",
    "szary": "grey",
    "ciemny szary": "dark grey",
    "czarny": "black",
}

# szablon opisu i dozwolone kolory dla każdej części
COLOR_TEMPLATES = {
    "leaf": "a photo of a plant with {} leaves.",
    "flower": "a photo of {} flowers.",
    "fruit": "a photo of {} fruits.",
    "hat": "a photo of a mushroom with a {} cap.",
    "stalk": "a photo of a tree with {} bark.",
}

COLORS_FOR = {
    "leaf": ["jasny zielony", "zielony", "ciemny zielony", "oliwkowy", "szary", "zolty",
             "czerwony", "burgundowy", "purpurowy", "brazowy"],
    "flower": [k for k in COLOR_WORDS if k not in ("oliwkowy", "ciemny szary", "ciemny zielony")],
    "fruit": list(COLOR_WORDS),
    "hat": ["bialy", "kremowy", "bezowy", "zolty", "zloty", "pomaranczowy", "czerwony",
            "brazowy", "ciemny brazowy", "szary", "oliwkowy", "zielony", "fioletowy", "czarny"],
    "stalk": ["bialy", "szary", "ciemny szary", "brazowy", "ciemny brazowy", "ciemny czerwony",
              "zielony", "czarny"],
}

# ---------------------------------------------------------------------
#  Kształty: pełne opisy dla każdej części
# ---------------------------------------------------------------------

SHAPES_FOR = {
    "leaf": {
        "okragly": "a photo of a plant with round leaves.",
        "owalny jajowaty": "a photo of a plant with oval, egg-shaped leaves.",
        "lezkowaty": "a photo of a plant with teardrop-shaped leaves.",
        "trojkatny grotowaty": "a photo of a plant with triangular, arrow-shaped leaves.",
        "sercowaty": "a photo of a plant with heart-shaped leaves.",
        "liniowy wydluzony": "a photo of a plant with long, narrow, linear leaves.",
        "nieregularny": "a photo of a plant with irregular, deeply lobed leaves.",
        "pierzasty": "a photo of a plant with pinnate, feather-like compound leaves.",
        "polkolisty nerkowaty": "a photo of a plant with kidney-shaped leaves.",
        "koniczynowaty": "a photo of a plant with clover-like leaves made of three leaflets.",
    },
    "flower": {
        "okragly": "a photo of round, flat, daisy-like flowers.",
        "kulisty": "a photo of globular, ball-shaped flower heads.",
        "baldachimowaty": "a photo of tiny flowers in flat umbrella-shaped clusters.",
        "lejowaty": "a photo of funnel-shaped, trumpet-like flowers.",
        "liniowy wydluzony": "a photo of flowers in long narrow spikes or catkins.",
        "nieregularny": "a photo of irregular, asymmetric flowers.",
        "lezkowaty": "a photo of drooping bell-shaped flowers.",
    },
    "fruit": {
        "kulisty": "a photo of small round berries.",
        "okragly": "a photo of round fruits.",
        "owalny jajowaty": "a photo of oval fruits.",
        "lezkowaty": "a photo of teardrop-shaped fruits.",
        "gruszkowaty": "a photo of pear-shaped fruits.",
        "liniowy wydluzony": "a photo of long narrow pods or elongated fruits.",
        "trojkatny grotowaty": "a photo of triangular fruits.",
        "nieregularny": "a photo of irregularly shaped fruits.",
    },
    "hat": {
        "okragly": "a photo of a mushroom with a flat round cap.",
        "kulisty": "a photo of a mushroom with a ball-shaped cap.",
        "polkolisty nerkowaty": "a photo of a mushroom with a hemispherical, convex cap.",
        "lejowaty": "a photo of a mushroom with a funnel-shaped cap.",
        "nieregularny": "a photo of a mushroom with an irregular, wavy cap.",
        "owalny jajowaty": "a photo of a mushroom with an egg-shaped cap.",
    },
}

# ---------------------------------------------------------------------
#  Powierzchnie
# ---------------------------------------------------------------------

SURFACE_WORDS = {
    "gladka": "smooth",
    "szorstki": "rough",
    "kolczasty": "spiny, thorny",
    "wilgotny": "wet, slimy",
    "suchy": "dry",
    "welurowy omszaly": "velvety, fuzzy",
    "woskowy": "waxy",
    "pomarszczony": "wrinkled",
    "blyszczacy": "glossy, shiny",
    "matowy": "matte",
    "delikatne gietkie wloski": "covered with fine soft hairs",
}

SURFACE_TEMPLATES = {
    "leaf": "a photo of a plant with {} leaves.",
    "fruit": "a photo of {} fruits.",
    "hat": "a photo of a mushroom with a {} cap.",
}

SURFACES_FOR = {
    "leaf": ["gladka", "szorstki", "kolczasty", "welurowy omszaly", "woskowy", "pomarszczony",
             "blyszczacy", "matowy", "delikatne gietkie wloski"],
    "fruit": ["gladka", "szorstki", "kolczasty", "welurowy omszaly", "woskowy", "pomarszczony",
              "blyszczacy", "matowy", "suchy"],
    "hat": ["gladka", "szorstki", "wilgotny", "suchy", "welurowy omszaly", "pomarszczony",
            "blyszczacy", "matowy"],
}

# ---------------------------------------------------------------------
#  Pola Tak/Nie: (opis "tak", opis "nie")
# ---------------------------------------------------------------------

FLAGS = {
    ("hat", "hasSpots"): (
        ["a photo of a mushroom with white spots on its cap."],
        ["a photo of a mushroom with a plain cap without spots."]),
    ("leaf", "hasSpots"): (
        ["a photo of leaves with dark spots."],
        ["a photo of plain, evenly colored leaves."]),
}
