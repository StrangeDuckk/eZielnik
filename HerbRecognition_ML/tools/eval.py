"""
Test trafności rozpoznawania na własnych zdjęciach – tabela do pracy inżynierskiej.

Wysyła każde zdjęcie do API eZielnika (POST api/recognize) i porównuje wynik
z oczekiwaną nazwą łacińską z pliku etykiet. Liczy trafność osobno dla każdego
z trzech głosów i dla wyniku głosowania.

Uruchomienie (tylko biblioteka standardowa Pythona, bez instalowania pakietów):
    python HerbRecognition_ML/tools/eval.py --api http://localhost:5000 \
        --photos zdjecia --labels zdjecia/etykiety.csv --out wyniki

Plik etykiet (CSV, przecinek): plik,nazwa_lacinska
    brzoza.webp,Betula pendula
    poza/roza.webp,Rosa          <- sam rodzaj = wystarczy zgodny rodzaj
"""

import argparse
import csv
import json
import mimetypes
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from pathlib import Path

SOURCES = [
    ("bioclip-photo", "BioCLIP – zdjęcie"),
    ("bioclip-form", "BioCLIP – formularz"),
    ("plantclef-photo", "PlantCLEF – zdjęcie"),
]


# ---------------------------------------------------------------------
#  Porównywanie nazw (ta sama zasada co w serwisie ml)
# ---------------------------------------------------------------------

def canonical(name: str | None, synonyms: dict[str, str]) -> str:
    if not name:
        return ""
    tokens = name.replace("×", " ").replace(" x ", " ").split()
    tokens = [t for t in tokens if t not in ("×",)]
    words = [tokens[0]] if tokens else []
    if len(tokens) > 1 and tokens[1][:1].islower() and not tokens[1].endswith("."):
        words.append(tokens[1])
    key = " ".join(words).lower()
    key = "".join(c for c in unicodedata.normalize("NFKD", key) if not unicodedata.combining(c))
    return synonyms.get(key, key)


def load_synonyms(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            left, right = (canonical(p, {}) for p in line.split("=", 1))
            if left and right:
                result[left] = right
    return result


def matches(predicted: str | None, expected: str, synonyms) -> bool:
    exp = canonical(expected, synonyms)
    pred = canonical(predicted, synonyms)
    if not exp or not pred:
        return False
    if " " not in exp:                      # w etykiecie sam rodzaj
        return pred.split(" ")[0] == exp
    return pred == exp


# ---------------------------------------------------------------------

def post_photo(api: str, path: Path) -> dict:
    boundary = uuid.uuid4().hex
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    if not mime.startswith("image/"):
        mime = "image/jpeg"

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="photo"; filename="{path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()

    request = urllib.request.Request(
        api.rstrip("/") + "/api/recognize", data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})

    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:5000")
    parser.add_argument("--photos", required=True, type=Path)
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--out", default=Path("wyniki-rozpoznawania"), type=Path)
    parser.add_argument("--synonyms", default=Path(__file__).resolve().parent.parent / "data" / "synonyms.txt", type=Path)
    args = parser.parse_args()

    synonyms = load_synonyms(args.synonyms)

    with open(args.labels, encoding="utf-8-sig", newline="") as f:
        labels = [(row[0].strip(), row[1].strip()) for row in csv.reader(f) if len(row) >= 2 and row[0].strip()
                  and not row[0].startswith("#") and row[0].strip().lower() != "plik"]

    rows = []
    for file_name, expected in labels:
        path = args.photos / file_name
        if not path.exists():
            print(f"! brak pliku {path}")
            continue

        try:
            result = post_photo(args.api, path)
        except urllib.error.HTTPError as ex:
            print(f"! {file_name}: HTTP {ex.code} {ex.read().decode(errors='replace')[:200]}")
            continue

        votes = {v["source"]: v for v in result.get("votes", [])}
        final = (result.get("final") or {}).get("latinName")

        row = {
            "plik": file_name,
            "oczekiwana": expected,
            "wynik": final or "—",
            "status": result.get("status"),
            "pewnosc": round(result.get("confidence", 0), 3),
            "wynik_ok": matches(final, expected, synonyms),
            "czas_s": round(result.get("durationMs", 0) / 1000, 1),
        }
        for source, _ in SOURCES:
            vote = votes.get(source) or {}
            choice = (vote.get("choice") or {}).get("latinName")
            row[f"{source}"] = choice if vote.get("voted") else f"({choice or '—'}, bez głosu)"
            row[f"{source}_ok"] = bool(vote.get("voted")) and matches(choice, expected, synonyms)
            row[f"{source}_glosowal"] = bool(vote.get("voted"))
        rows.append(row)

        mark = "✓" if row["wynik_ok"] else "✗"
        print(f"{mark} {file_name}: oczekiwano {expected}, wynik {row['wynik']} ({row['status']}, {row['czas_s']} s)")
        time.sleep(0.5)

    if not rows:
        print("Brak wyników.")
        return

    args.out.mkdir(parents=True, exist_ok=True)

    # ----- CSV ze wszystkim -----
    with open(args.out / "wyniki.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # ----- tabela do pracy (Markdown) -----
    def pct(ok: int, total: int) -> str:
        return f"{ok}/{total} ({100 * ok / total:.0f}%)" if total else "—"

    lines = ["# Trafność rozpoznawania ze zdjęcia", "",
             f"Zdjęć: {len(rows)}", "",
             "| Głos | Trafne (z oddanych głosów) | Trafne (ze wszystkich zdjęć) |",
             "|---|---|---|"]
    for source, title in SOURCES:
        voted = [r for r in rows if r[f"{source}_glosowal"]]
        ok = sum(r[f"{source}_ok"] for r in rows)
        lines.append(f"| {title} | {pct(ok, len(voted))} | {pct(ok, len(rows))} |")
    ok_final = sum(r["wynik_ok"] for r in rows)
    lines.append(f"| **Wynik głosowania** | {pct(ok_final, len(rows))} | {pct(ok_final, len(rows))} |")

    lines += ["", "| Zdjęcie | Oczekiwana | Wynik | BioCLIP zdj. | BioCLIP form. | PlantCLEF | Status |",
              "|---|---|---|---|---|---|---|"]
    for r in rows:
        def cell(src):
            return ("✓ " if r[f"{src}_ok"] else "") + str(r[src])
        lines.append(f"| {r['plik']} | {r['oczekiwana']} | {'✓ ' if r['wynik_ok'] else '✗ '}{r['wynik']} | "
                     f"{cell('bioclip-photo')} | {cell('bioclip-form')} | {cell('plantclef-photo')} | {r['status']} |")

    (args.out / "wyniki.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:10]))
    print(f"\nZapisano: {args.out / 'wyniki.md'} i {args.out / 'wyniki.csv'}")


if __name__ == "__main__":
    main()
