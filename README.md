# Systém pro detekci TV reklam

Tento projekt je systém pro detekci a extrakci televizních reklam z živého vysílání. Skládá se z několika Python skriptů, které spolupracují na zpracování video souborů a identifikaci reklamních segmentů.

## Komponenty
### stream_downloader.py
- Stahuje živé vysílání z IPTV streamů
- Ukládá nahrávky do půlhodinových souborů ve formátu MP4
- Automaticky vytváří záznamy v MongoDB s informacemi o nahrávce
- Zajišťuje kontinuální nahrávání s minimálními výpadky

### segment_finder.py
- Hlavní skript pro detekci reklamních segmentů ve videích
- Využívá analýzu zvuku a obrazu k identifikaci potenciálních reklamních bloků
- Detekuje černé snímky a tiché úseky, které typicky označují hranice reklam
- Ukládá detekované segmenty do MongoDB se statusem 'detected'

### segment_extractor.py
- Zpracovává segmenty označené jako 'detected' v databázi
- Používá ffmpeg pro vystřižení identifikovaných reklamních segmentů ze zdrojových videí
- Ukládá extrahované segmenty jako samostatné MP4 soubory
- Aktualizuje status segmentu na 'saved' při úspěšné extrakci
- Zpracovává chyby a aktualizuje status podle potřeby

### segment_length_validator.py
- Validuje délku extrahovaných reklamních segmentů
- Kontroluje, zda je délka segmentu dělitelná 5 sekundami (běžná délka reklam)
- Aktualizuje segmenty na status 'approved' nebo 'needs_review'
- Pomáhá filtrovat falešné detekce a nepravidelné segmenty

### upload_to_cloud.py
- Nahrává schválené segmenty do cloudového úložiště (cgs)
- Nastavuje status na 'uploaded' po dokončení přenosu


## Pracovní postup
1. segment_finder.py analyzuje video soubory a detekuje potenciální reklamní segmenty
2. segment_extractor.py vystřihne detekované segmenty do samostatných souborů
3. segment_length_validator.py validuje segmenty podle jejich délky
4. upload_to_cloud.py nahraje segmenty na cloud

## Struktura databáze
Schéma MongoDB vypaá nasledovně:
 - TV
     - records
        - "_id": ObjectId("66f090909090909090909090"),
        - "source": "prima_cool",
        - "start_at": datetime.now(),
        - "file_path": "http://ravineo-tv/prima_cool/stream_20250327_123456/stream_20250327_123456.mp4",
        - "status": "downloaded", # downloaded, processed
    - segments
        -  "_id": ObjectId("66f090909090909090909091"),

        - "record_id": ObjectId("66f090909090909090909090"),
        - "source": "prima_cool",
        - "record_file_path": "http://ravineo-tv/prima_cool/stream_20250327_123456/stream_20250327_123456.mp4",

        - "start_at": datetime.now(),
        - "end_at": datetime.now(),
        - "start_secs": 100.5,
        - "end_secs": 200.5,

        - "file_path": "http://ravineo-tv/prima_cool/stream_20250327_123456/stream_20250327_123456.mp4",

        - "status": "detected", # detected, extracted, confirmed, rejected


