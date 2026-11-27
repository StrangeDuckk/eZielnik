"""
Nazwy łacińskie: obcinanie autorów i porównywanie nazw z różnych źródeł.

"Mentha × piperita L."  -> wyświetlana: "Mentha × piperita", klucz: "mentha piperita"
"Taraxacum officinale F.H.Wigg." -> "Taraxacum officinale", klucz: "taraxacum officinale"
"""

import unicodedata
from pathlib import Path

_HYBRID = {"×", "x", "X"}

_synonyms: dict[str, str] = {}


def display_name(name: str | None) -> str:
    """Rodzaj + (×) + epitet gatunkowy, bez autora i rang poniżej gatunku."""
    if not name:
        return ""

    tokens = name.replace("×", " × ").split()
    if not tokens:
        return ""

    out = [tokens[0].capitalize()]
    i = 1

    if i < len(tokens) and tokens[i] in _HYBRID:
        out.append("×")
        i += 1

    if i < len(tokens) and tokens[i][:1].islower() and not tokens[i].endswith("."):
        out.append(tokens[i])

    return " ".join(out)


def canonical(name: str | None) -> str:
    """Klucz do porównań: małe litery, bez znaku krzyżówki i znaków diakrytycznych."""
    shown = display_name(name).replace("×", " ")
    shown = unicodedata.normalize("NFKD", shown)
    shown = "".join(c for c in shown if not unicodedata.combining(c))
    key = " ".join(shown.lower().split())
    return _synonyms.get(key, key)


def load_synonyms(path: Path) -> None:
    """Plik: jedna para w linii "nazwa = nazwa_używana_w_bazie"."""
    _synonyms.clear()
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" not in line:
            continue
        left, right = (canonical(part) for part in line.split("=", 1))
        if left and right and left != right:
            _synonyms[left] = right
