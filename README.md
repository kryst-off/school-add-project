# Systém pro detekci TV reklam

Tento projekt je systém pro detekci a extrakci televizních reklam z živého vysílání. Skládá se z několika Python skriptů, které spolupracují na zpracování video souborů a identifikaci reklamních segmentů.

## Instalace a spuštění

### Předpoklady
- Python 3.12 nebo novější
- Poetry (správce závislostí pro Python)
- MongoDB databáze

### Instalace Poetry
1. Instalace Poetry (pokud ještě není nainstalován):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Ověření instalace:
```bash
poetry --version
```

### Nastavení projektu
1. Klonování repozitáře:
```bash
git clone <url-repozitáře>
cd school-project
```

2. Vytvoření a aktivace virtuálního prostředí pomocí Poetry:
```bash
poetry install
poetry shell
```

3. Nastavení proměnných prostředí:
- Vytvořte soubor `.env` v kořenovém adresáři projektu
- Přidejte do něj potřebné proměnné prostředí MONGODB_URI a INPUT_URL

## Komponenty
### stream_downloader.py
- Stahuje živé vysílání z IPTV streamů
- Ukládá nahrávky do půlhodinových souborů ve formátu MP4
- Automaticky vytváří záznamy v MongoDB s informacemi o nahrávce
- Zajišťuje kontinuální nahrávání s minimálními výpadky (smyčka v `__main__.py`)
```bash
python -m school_project.__main__.py
```

### segment_finder.py
- Hlavní skript pro detekci reklamních segmentů ve videích
- Využívá analýzu zvuku a obrazu k identifikaci potenciálních reklamních bloků
- Detekuje černé snímky a tiché úseky, které typicky označují hranice reklam
- Ukládá detekované segmenty do MongoDB se statusem 'detected'
```bash
python -m school_project.segment_finder
```

### segment_extractor.py
- Zpracovává segmenty označené jako 'detected' v databázi
- Používá ffmpeg pro vystřižení identifikovaných reklamních segmentů ze zdrojových videí
- Ukládá extrahované segmenty jako samostatné MP4 soubory
- Aktualizuje status segmentu na 'saved' při úspěšné extrakci
- Zpracovává chyby a aktualizuje status podle potřeby
```bash
python -m school_project.segment_extractor
```

### segment_length_validator.py
- Validuje délku extrahovaných reklamních segmentů
- Kontroluje, zda je délka segmentu dělitelná 5 sekundami (běžná délka reklam)
- Aktualizuje segmenty na status 'approved' nebo 'needs_review'
- Pomáhá filtrovat falešné detekce a nepravidelné segmenty
```bash
python -m school_project.segment_length_validator
```

### upload_to_cloud.py
- Nahrává schválené segmenty do cloudového úložiště (cgs)
- Nastavuje status na 'uploaded' po dokončení přenosu
```bash
python -m school_project.upload_to_gcs
```


## Pracovní postup
1. segment_finder.py analyzuje video soubory a detekuje potenciální reklamní segmenty
2. segment_extractor.py vystřihne detekované segmenty do samostatných souborů
3. segment_length_validator.py validuje segmenty podle jejich délky
4. upload_to_cloud.py nahraje segmenty na Google Cloud Storage

## Struktura databáze

Databáze obsahuje dvě hlavní kolekce: `records` a `segments`.

### Kolekce: records
Záznamy o stažených video souborech.

| Pole | Typ | Popis |
|------|-----|--------|
| _id | ObjectId | Unikátní identifikátor záznamu |
| source | string | Zdroj streamu (např. "prima_cool") |
| start_at | datetime | Čas začátku nahrávky |
| file_path | string | Cesta k souboru (URL) |
| status | string | Status záznamu ("downloaded", "processed") |

### Kolekce: segments
Detekované a zpracované reklamní segmenty.

| Pole | Typ | Popis |
|------|-----|--------|
| _id | ObjectId | Unikátní identifikátor segmentu |
| record_id | ObjectId | Reference na záznam v kolekci records |
| source | string | Zdroj streamu |
| record_file_path | string | Cesta k původnímu souboru |
| start_at | datetime | Čas začátku segmentu |
| end_at | datetime | Čas konce segmentu |
| start_secs | float | Začátek segmentu v sekundách |
| end_secs | float | Konec segmentu v sekundách |
| duration_secs | float | Délka segmentu v skundách |
| file_path | string | Cesta k extrahovanému segmentu |
| status | string | Status segmentu ("detected", "extracted", "confirmed", "rejected") |


