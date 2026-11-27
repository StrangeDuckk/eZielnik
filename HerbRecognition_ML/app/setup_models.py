"""
Przygotowanie plików modeli – uruchamiane przy starcie kontenera, przed serwerem.
Robi coś tylko wtedy, gdy plików jeszcze nie ma (kolejne starty trwają sekundę).

1. BioCLIP: pobiera wagi z Hugging Face do HF_HOME (wolumen).
2. PlantCLEF: pobiera archiwum z Zenodo (2,3 GB, ze wznawianiem po zerwaniu
   połączenia i sprawdzeniem MD5), wyciąga jeden model, zapisuje same wagi
   (model.pt) i usuwa archiwum.
3. PlantCLEF: buduje species_names.csv (numer gatunku -> nazwa łacińska)
   z pliku metadanych zbioru treningowego, czytanego w strumieniu.

Błąd przy PlantCLEF nie zatrzymuje serwisu – działa wtedy sam BioCLIP (2 głosy).
Ręcznie: docker compose exec ml python -m app.setup_models
"""

import csv
import hashlib
import http.client
import io
import logging
import shutil
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import plantclef, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s setup: %(message)s")
log = logging.getLogger("setup")

USER_AGENT = "eZielnik-setup/1.0"


def _open(url: str, headers: dict | None = None):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    return urllib.request.urlopen(request, timeout=120)


DOWNLOAD_ERRORS = (urllib.error.URLError, http.client.HTTPException, ConnectionError, TimeoutError, OSError)


def download(url: str, target: Path, md5: str | None = None, attempts: int = 20) -> None:
    """
    Pobiera duży plik na dysk. Gdy serwer zerwie połączenie (Zenodo robi to przy
    dużych plikach), wznawia od miejsca przerwania (nagłówek Range), a nie od zera.
    Na końcu sprawdza sumę MD5, żeby nie rozpakowywać uciętego archiwum.
    """
    part = target.with_name(target.name + ".part")

    # liczymy tylko próby, w których nic nie przybyło – postęp zeruje licznik
    attempt = 0
    while True:
        attempt += 1
        have = part.stat().st_size if part.exists() else 0
        started_at = have
        headers = {"Range": f"bytes={have}-"} if have else {}

        try:
            with _open(url, headers) as response:
                resumed = have > 0 and response.status == 206
                if have and not resumed:
                    log.info("Serwer nie obsługuje wznawiania – pobieranie od początku")
                    have = 0

                remaining = int(response.headers.get("Content-Length") or 0)
                total = have + remaining
                next_log = have + 200_000_000

                with open(part, "ab" if resumed else "wb") as f:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        have += len(chunk)
                        if have >= next_log:
                            log.info("  pobrano %d / %d MB", have // 1_000_000, total // 1_000_000)
                            next_log += 200_000_000

                if total and have < total:
                    raise ConnectionError(f"połączenie zerwane po {have // 1_000_000} MB")

            break   # pobrane w całości

        except urllib.error.HTTPError as ex:
            if ex.code == 416 and have:   # "zakres poza plikiem" = mamy już cały plik
                break
            if attempt >= attempts:
                raise
            log.warning("Pobieranie: HTTP %s – ponowna próba %d/%d", ex.code, attempt + 1, attempts)
            time.sleep(min(60, 5 * attempt))

        except DOWNLOAD_ERRORS as ex:
            current = part.stat().st_size if part.exists() else 0
            if current > started_at:
                attempt = 0   # coś się pobrało – to nie jest "zawieszone" pobieranie
            if attempt >= attempts:
                raise
            log.warning("Pobieranie przerwane (%s) – wznawiam od %d MB", ex, current // 1_000_000)
            time.sleep(min(60, 5 * max(attempt, 1)))

    if md5:
        log.info("Sprawdzanie sumy kontrolnej …")
        digest = hashlib.md5()
        with open(part, "rb") as f:
            for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != md5.lower():
            part.unlink(missing_ok=True)
            raise RuntimeError("Pobrany plik jest uszkodzony (zła suma MD5) – przy następnym starcie pobierze się od nowa.")

    part.replace(target)


# ---------------------------------------------------------------------
#  BioCLIP
# ---------------------------------------------------------------------

def setup_bioclip() -> None:
    import open_clip
    log.info("BioCLIP: sprawdzanie / pobieranie %s", settings.BIOCLIP_MODEL)
    # pobiera pliki do HF_HOME, jeśli ich nie ma; model zaraz jest zwalniany
    model, _, _ = open_clip.create_model_and_transforms(settings.BIOCLIP_MODEL)
    del model
    log.info("BioCLIP: OK")


# ---------------------------------------------------------------------
#  PlantCLEF – wagi
# ---------------------------------------------------------------------

def setup_plantclef_weights(folder: Path) -> None:
    model_file = folder / plantclef.MODEL_FILE
    mapping_file = folder / plantclef.MAPPING_FILE
    if model_file.exists() and mapping_file.exists():
        log.info("PlantCLEF: wagi już są")
        return

    folder.mkdir(parents=True, exist_ok=True)
    checkpoint = folder / "model_best.pth.tar"

    if not checkpoint.exists() or not mapping_file.exists():
        archive_file = folder / "plantclef2024.tar"
        if not archive_file.exists():
            log.info("PlantCLEF: pobieranie archiwum z Zenodo (ok. 2,3 GB, kilka–kilkanaście minut) …")
            download(settings.PLANTCLEF_ZENODO_URL, archive_file, settings.PLANTCLEF_ZENODO_MD5)

        log.info("PlantCLEF: rozpakowywanie modelu %s …", settings.PLANTCLEF_VARIANT)
        names_in_archive: list[str] = []
        mapping_in_variant = False

        with tarfile.open(archive_file, mode="r:*") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                path = member.name.replace("\\", "/")
                names_in_archive.append(path)
                parts = path.split("/")
                file_name = parts[-1]
                in_variant = len(parts) >= 2 and parts[-2] == settings.PLANTCLEF_VARIANT

                # wagi: tylko z folderu wybranego wariantu
                # class_mapping.txt: z folderu wariantu, a jeśli go tam nie ma – wspólny (np. w głównym folderze archiwum)
                # species_id_to_name.txt: jeśli jest w archiwum, nie trzeba pobierać metadanych zbioru
                if file_name == "model_best.pth.tar" and in_variant:
                    target = checkpoint
                elif file_name == plantclef.MAPPING_FILE and (in_variant or not mapping_in_variant):
                    target = mapping_file
                    mapping_in_variant = mapping_in_variant or in_variant
                elif file_name == "species_id_to_name.txt":
                    target = folder / file_name
                else:
                    continue

                part_file = folder / (file_name + ".part")
                log.info("PlantCLEF: zapisywanie %s (%d MB)", path, member.size // 1_000_000)
                with archive.extractfile(member) as src, open(part_file, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                part_file.replace(target)

        if not checkpoint.exists() or not mapping_file.exists():
            log.error("PlantCLEF: pliki w archiwum:\n  %s", "\n  ".join(names_in_archive))
            raise RuntimeError(
                f"W archiwum nie znaleziono modelu {settings.PLANTCLEF_VARIANT} "
                "(model_best.pth.tar + class_mapping.txt).")

        archive_file.unlink(missing_ok=True)   # 2,3 GB mniej na dysku

    log.info("PlantCLEF: zapisywanie samych wag (bez stanu treningu) …")
    import torch
    try:
        state = torch.load(checkpoint, map_location="cpu", weights_only=False, mmap=True)
    except RuntimeError:
        state = torch.load(checkpoint, map_location="cpu", weights_only=False)

    # wagi EMA (średnia z treningu) są według autorów dokładniejsze
    weights = state.get("state_dict_ema") or state.get("state_dict") or state
    weights = {k.removeprefix("module."): v for k, v in weights.items()}
    part_file = folder / (plantclef.MODEL_FILE + ".part")
    torch.save(weights, part_file)
    part_file.replace(model_file)
    del state, weights

    checkpoint.unlink(missing_ok=True)
    log.info("PlantCLEF: wagi gotowe (%d MB)", model_file.stat().st_size // 1_000_000)


# ---------------------------------------------------------------------
#  PlantCLEF – nazwy gatunków
# ---------------------------------------------------------------------

def setup_plantclef_names(folder: Path) -> None:
    names_file = folder / plantclef.NAMES_FILE
    if names_file.exists():
        log.info("PlantCLEF: nazwy gatunków już są")
        return

    wanted = set(plantclef.read_class_mapping(folder / plantclef.MAPPING_FILE))
    found: dict[str, str] = {}

    # 1) plik z nazwami z archiwum modelu (jeśli był)
    local = folder / "species_id_to_name.txt"
    if local.exists():
        text = local.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        header = lines[0] if lines else ""
        delimiter = ";" if header.count(";") >= max(header.count(","), header.count("\t")) else \
            ("\t" if header.count("\t") > header.count(",") else ",")
        for row in csv.reader(lines, delimiter=delimiter):
            if len(row) >= 2 and row[0].strip() in wanted:
                found.setdefault(row[0].strip(), row[1].strip())
        log.info("PlantCLEF: nazwy z species_id_to_name.txt: %d/%d", len(found), len(wanted))

    # 2) brakujące – z metadanych zbioru treningowego
    for attempt in range(1, 6):
        if len(found) == len(wanted):
            break
        try:
            _read_species_names(wanted, found)
            break
        except DOWNLOAD_ERRORS as ex:
            if len(found) == len(wanted) or attempt == 5:
                raise
            log.warning("Czytanie nazw przerwane (%s) – ponowna próba %d/5", ex, attempt + 1)
            time.sleep(10 * attempt)

    tmp = folder / (plantclef.NAMES_FILE + ".part")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["species_id", "species"])
        for sid in sorted(found, key=lambda s: int(s) if s.isdigit() else s):
            writer.writerow([sid, found[sid]])
    tmp.replace(names_file)
    log.info("PlantCLEF: zapisano nazwy %d/%d gatunków", len(found), len(wanted))


def _read_species_names(wanted: set[str], found: dict[str, str]) -> None:
    log.info("PlantCLEF: czytanie nazw gatunków z %s …", settings.PLANTCLEF_CSV_URL)
    with _open(settings.PLANTCLEF_CSV_URL) as response:
        lines = io.TextIOWrapper(response, encoding="utf-8", errors="replace", newline="")
        header = lines.readline()
        delimiter = ";" if header.count(";") > header.count(",") else ","
        columns = [c.strip().strip('"') for c in header.split(delimiter)]

        try:
            id_col = columns.index("species_id")
            name_col = columns.index("species")
        except ValueError:
            raise RuntimeError(f"W pliku CSV brak kolumn species_id / species. Kolumny: {columns}")

        for i, row in enumerate(csv.reader(lines, delimiter=delimiter)):
            if len(row) <= max(id_col, name_col):
                continue
            sid = row[id_col].strip()
            if sid in wanted and sid not in found:
                found[sid] = row[name_col].strip()
                if len(found) == len(wanted):
                    break   # mamy wszystkie – nie trzeba czytać reszty pliku
            if i % 200_000 == 0 and i:
                log.info("PlantCLEF: przeczytano %d wierszy, gatunków %d/%d", i, len(found), len(wanted))


# ---------------------------------------------------------------------

def main() -> int:
    settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        setup_bioclip()
    except Exception:
        log.exception("BioCLIP: nie udało się pobrać modelu")
        return 1   # bez BioCLIP serwis nie ma sensu – kontener spróbuje ponownie

    if settings.PLANTCLEF_ENABLED:
        try:
            setup_plantclef_weights(settings.PLANTCLEF_DIR)
            setup_plantclef_names(settings.PLANTCLEF_DIR)
        except Exception:
            log.exception("PlantCLEF: przygotowanie nie powiodło się – serwis ruszy z samym BioCLIP")

    return 0


if __name__ == "__main__":
    sys.exit(main())
