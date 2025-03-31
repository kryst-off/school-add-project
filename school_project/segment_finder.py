import av
import logging
import time
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

def detect_silent_black_segments(video_path: str, record: dict) -> None:
    """
    Detekuje segmenty ve videu, které jsou současně černé a tiché.
    Zapisuje hranice mezi segmenty pro následné vystřižení.
    
    Args:
        video_path: Cesta k video souboru
        record: MongoDB záznam obsahující metadata o videu
    """
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
            
            if is_black and is_silent:
                logger.info(f'Black and silent at {format_time(video_time)}')

            # Stavový stroj
            if is_black and is_silent and not in_silent_black_segment:
                segment_start = video_time
                in_silent_black_segment = True

            elif in_silent_black_segment and (not is_black or not is_silent):
                # Kontrola minimální délky mezi segmenty
                if last_segment_end is not None:
                    segment_gap = segment_start - last_segment_end
                    if segment_gap < 1.0 or segment_gap > 120.0:  # Minimální mezera 1s, maximální 120s
                        in_silent_black_segment = False
                        segment_start = None
                        continue
                    
                # Pokud máme předchozí konec segmentu, zapíšeme hranici
                if last_segment_end is not None:
                    output_file = Path(video_path).parent / f"silent_black_segments_{Path(video_path).stem}.txt"
                    start_pts = int(last_segment_end / float(video_stream.time_base))
                    end_pts = int(segment_start / float(video_stream.time_base))
                    with open(output_file, 'a', encoding='utf-8') as f:
                        f.write(f"{start_pts} {end_pts}\n")
                    logger.info(f"Segment boundary: {format_time(last_segment_end)} - {format_time(segment_start)}")

                    # Get original video date from record
                    video_date = record["start_at"]
                    # Calculate segment timestamp using video date and segment start time
                    segment_date = video_date + timedelta(seconds=last_segment_end)
                    # Create output filename using segment timestamp
                    timestamp = segment_date.strftime('%Y%m%d_%H%M%S')
                    output_filename = Path(video_path).parent / f'segment_{timestamp}.mp4'

                    myclient = pymongo.MongoClient("mongodb://localhost:27017/")
                    mydb = myclient["tv"]
                    mycol = mydb["segments"]
                    segment_record = {
                        "record_id": record["_id"],
                        "source": record["source"],
                        "record_file_path": record["file_path"],

                        "start_at": record["start_at"] + timedelta(seconds=last_segment_end),
                        "end_at": record["start_at"] + timedelta(seconds=segment_start),
                        "start_secs": last_segment_end,
                        "end_secs": segment_start,
                        "duration_secs": segment_start - last_segment_end,

                        # "file_path": str(output_filename),

                        "status": "detected",
                    }
                    mycol.insert_one(segment_record)

                last_segment_end = video_time
                in_silent_black_segment = False
                segment_start = None
                
    except Exception as e:
        logger.error(f"Error processing video: {e}")
    finally:
        myclient = pymongo.MongoClient("mongodb://localhost:27017/")
        mydb = myclient["tv"]
        mycol = mydb["records"]
        mycol.update_one({"_id": record["_id"]}, {"$set": {"status": "detected"}})
        logger.info(f"Updated record status to 'detected'")
        container.close()

if __name__ == "__main__":
    myclient = pymongo.MongoClient("mongodb://localhost:27017/")
    mydb = myclient["tv"]
    mycol = mydb["records"]
    records = mycol.find({"status": "downloaded"})

    for record in records:
        video_file = record["file_path"]
        
        detect_silent_black_segments(str(video_file), record)
