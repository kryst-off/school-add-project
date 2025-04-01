import av
import logging
from pathlib import Path
import pymongo
from datetime import timedelta

from school_project.detection import SilenceDetector, analyze_video_frame

# Nastavení loggeru
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("video_cut")

def format_time(seconds: float) -> str:
    """
    Formátuje čas v sekundách do formátu mm:ss.ssss
    """
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    return f"{minutes:02d}:{remaining_seconds:06.3f}"

def detect_silent_black_segments(video_path: str, record: dict, db_client: pymongo.MongoClient) -> None:
    """
    Detekuje segmenty ve videu, které jsou současně černé a tiché.
    Zapisuje hranice mezi segmenty pro následné vystřižení.
    
    Args:
        video_path: Cesta k video souboru
        record: MongoDB záznam obsahující metadata o videu
        db_client: Připojení k MongoDB
    """
    container = None
    try:
        logger.info(f"Opening video file: {video_path}")

        materials_path = Path("materials") / video_path
        video_path = str(materials_path)

        container = av.open(video_path)

        # Získání streamů
        audio_stream = container.streams.audio[0]
        video_stream = container.streams.video[0]

        # Vytvoření detektoru ticha
        silence_detector = SilenceDetector(sample_rate=audio_stream.rate)
        
        is_black = False
        is_silent = False
        
        # Stavový stroj pro sledování segmentů
        segment_start = None
        last_segment_end = None
        in_silent_black_segment = False
        video_time = 0.0
        
        # Dekódování všech framů v jedné smyčce
        for frame in container.decode(audio=0, video=0):
            # Aktualizace času a stavu podle typu framu
            if isinstance(frame, av.VideoFrame):
                old_black = is_black
                is_black = analyze_video_frame(frame)
                video_time = frame.pts * float(video_stream.time_base)
                if old_black != is_black:
                    logger.info(f'Black {is_black} at {format_time(video_time)}')
                    
            elif isinstance(frame, av.AudioFrame):
                old_silent = is_silent
                is_silent = silence_detector.analyze_frame(frame)
                if old_silent != is_silent:
                    logger.info(f'Silent {is_silent} at {format_time(video_time)}')
            
            # Detekce začátku nového segmentu (přechod do černé a tiché části)
            if is_black and is_silent and not in_silent_black_segment:
                segment_start = video_time
                in_silent_black_segment = True
                logger.info(f"Potential segment start at {format_time(segment_start)}")

            # Detekce konce segmentu (přechod z černé a tiché části)
            elif in_silent_black_segment and (not is_black or not is_silent):
                segment_end = video_time
                
                # Validace segmentu pouze pokud už máme nějaký předchozí segment
                if last_segment_end is not None:
                    segment_gap = segment_start - last_segment_end
                    
                    # Kontrola, zda je mezera mezi segmenty v rozumném rozmezí
                    if 1.0 <= segment_gap <= 120.0:  # Minimální mezera 1s, maximální 120s
                        logger.info(f"Segment boundary: {format_time(last_segment_end)} - {format_time(segment_start)}")

                        # Vytvoření záznamu segmentu v databázi
                        save_segment_to_db(record, last_segment_end, segment_start, db_client)
                
                # Aktualizace poslední hodnoty pro další iteraci
                last_segment_end = segment_end
                in_silent_black_segment = False
                segment_start = None

        # Aktualizace statusu nahrávky po dokončení
        mydb = db_client["tv"]
        mycol = mydb["records"]
        mycol.update_one({"_id": record["_id"]}, {"$set": {"status": "detected"}})
        logger.info(f"Updated record status to 'detected'")
                
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        # Aktualizace statusu nahrávky po dokončení
        mydb = db_client["tv"]
        mycol = mydb["records"]
        mycol.update_one({"_id": record["_id"]}, {"$set": {"status": "error"}})
        logger.info(f"Updated record status to 'error'")
    finally:
        if container:
            container.close()

def save_segment_to_db(record, start_time, end_time, db_client):
    """
    Uloží informace o detekovaném segmentu do databáze.
    
    Args:
        record: Původní záznam videa
        start_time: Začátek segmentu v sekundách
        end_time: Konec segmentu v sekundách
        db_client: Připojení k MongoDB
    """
    # Uložení záznamu do MongoDB
    mydb = db_client["tv"]
    mycol = mydb["segments"]
    segment_record = {
        "record_id": record["_id"],
        "source": record["source"],
        "record_file_path": record["file_path"],

        "start_at": record["start_at"] + timedelta(seconds=start_time),
        "end_at": record["start_at"] + timedelta(seconds=end_time),
        "start_secs": start_time,
        "end_secs": end_time,
        "duration_secs": end_time - start_time,

        "status": "detected",
    }
    mycol.insert_one(segment_record)

if __name__ == "__main__":
    myclient = pymongo.MongoClient("mongodb://localhost:27017/")
    mydb = myclient["tv"]
    mycol = mydb["records"]
    records = mycol.find({"status": "downloaded"})

    for record in records:
        video_file = record["file_path"]
        detect_silent_black_segments(str(video_file), record, myclient)
