# HerbRecognition_ML – rozpoznawanie roślin ze zdjęcia

Część projektu **eZielnik** (praca inżynierska Katarzyny Mikusek).
Serwis działa tylko w wewnętrznej sieci Dockera. Korzysta z niego API eZielnika (`POST api/recognize`).

## Jak to działa

Dwa modele oddają trzy głosy:

| Głos | Model | Co robi |
|---|---|---|
| 1 | BioCLIP | porównuje zdjęcie z nazwami łacińskimi (rośliny z bazy + ~7800 gatunków PlantCLEF + grzyby z `data/fungi.txt`) |
| 2 | BioCLIP | wypełnia formularz cech (typ, kolor, kształt, powierzchnia, plamki), a wyszukiwarka eZielnika wskazuje roślinę z bazy |
| 3 | PlantCLEF 2024 | klasyfikator Pl@ntNet, 7806 gatunków roślin naczyniowych Europy (bez grzybów) |

Głosowanie odbywa się w API (`HerbRecognition_APIs/Services/RecognitionService.cs`), bo tylko API zna bazę.
Każdy model dzieli swój głos między kilka gatunków według swojej pewności. Głosy są mnożone przez wagi:
zdjęcie 1,0, formularz 0,6. Wygrywa gatunek z największą sumą.

## Pliki

```
app/main.py           serwer HTTP: GET /health, POST /analyze
app/service.py        ładowanie modeli i analiza zdjęcia
app/bioclip.py        model 1 + cache opisów tekstowych
app/plantclef.py      model 2
app/form_filler.py    wypełnianie formularza przez BioCLIP
app/form_prompts.py   opisy po angielsku dla wartości słowników z bazy
app/setup_models.py   pobranie modeli przy pierwszym starcie
app/settings.py       ustawienia (zmienne środowiskowe)
data/fungi.txt        grzyby spoza bazy, które BioCLIP bierze pod uwagę
data/synonyms.txt     synonimy nazw łacińskich
tools/eval.py         test trafności na własnych zdjęciach (tabela do pracy)
```

## Ustawienia (docker-compose / Coolify)

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `BIOCLIP_MODEL` | `hf-hub:imageomics/bioclip` | `hf-hub:imageomics/bioclip-2` jest dokładniejszy, ale potrzebuje ~1,7 GB RAM więcej |
| `PLANTCLEF_ENABLED` | `true` | `false` = tylko BioCLIP (2 głosy), ~0,4 GB RAM mniej |
| `PLANTCLEF_IMG_SIZE` | `518` | `392` = ok. 2× szybciej, minimalnie mniej dokładnie |
| `FORM_FIELD_MIN` | `0.40` | od jakiej pewności model wpisuje cechę do formularza |
| `FORM_TYPE_MIN` | `0.50` | to samo dla typu rośliny |

## Licencje modeli

- **BioCLIP** – Imageomics Institute, licencja MIT. https://huggingface.co/imageomics/bioclip
- **PlantCLEF 2024 pretrained models** – Pl@ntNet (Goëau, Espitalier, Bonnet, Joly), licencja CC BY 4.0.
  https://zenodo.org/records/10848263

Obie licencje wymagają podania autorów. Informacja jest na stronie „Rozpoznaj” w aplikacji i w tym pliku.
