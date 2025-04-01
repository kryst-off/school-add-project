import subprocess
import logging
import av
from pathlib import Path
import pymongo
# Nastavení loggeru
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("video_saw")

def cut_video_segments(video_path: str, segment: dict, db_client: pymongo.MongoClient) -> None:
    """
    Rozřeže video na segmenty podle PTS uvedených v textovém souboru.
    Používá FFmpeg pro kopírování streamů bez překódování.
    """
    try:
        # Otevření vstupního videa pro získání time_base
        materials_path = Path("materials") / video_path
        video_path = str(materials_path)

        input_container = av.open(video_path)
        video_stream = input_container.streams.video[0]
        time_base = float(video_stream.time_base)
        input_container.close()

        # Načtení PTS segmentů
        start_time = segment["start_secs"]
        end_time = segment["end_secs"]
        
        # Vytvoření výstupního adresáře
        output_dir = Path("materials") / segment["source"] / "segments"
        output_dir.mkdir(exist_ok=True)
        
        # Zpracování každého segmentu
        timestamp = segment["start_at"].strftime('%Y%m%d_%H%M%S')
        output_path = output_dir / f"segment_{timestamp}.mp4"
        logger.info(f"Cutting segment {segment["_id"]}: {start_time:.2f}s - {end_time:.2f}s")
        
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-ss", str(start_time),
            "-i", str(video_path),
            "-t", str(end_time - start_time),
            "-c:v", "libx264",         # Video kodek
            "-preset", "ultrafast",    # Nejrychlejší enkódování
            "-crf", "23",              # Rozumný kompromis kvality
            "-force_key_frames", "expr:gte(t,0)",  # Vynutí keyframe na začátku
            "-acodec", "aac",          # Překódovat audio místo kopírování
            "-avoid_negative_ts", "make_zero",
            "-y",
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Segment {segment["_id"]} saved to {output_path}")

            mydb = db_client["tv"]
            mycol = mydb["segments"]
            relative_path = Path(*output_path.parts[1:])
            mycol.update_one({"_id": segment["_id"]}, {"$set": {"status": "saved", "segment_file_path": str(relative_path)}})

        except subprocess.CalledProcessError as e:
            logger.error(f"Error cutting segment {segment["_id"]}: {e.stderr.decode()}")
            mydb = db_client["tv"]
            mycol = mydb["segments"]
            mycol.update_one({"_id": segment["_id"]}, {"$set": {"status": "error"}})
        
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        mydb = db_client["tv"]
        mycol = mydb["segments"]
        mycol.update_one({"_id": segment["_id"]}, {"$set": {"status": "error"}})

if __name__ == "__main__":
    myclient = pymongo.MongoClient("mongodb://localhost:27017/")
    mydb = myclient["tv"]
    mycol = mydb["segments"]
    segments = mycol.find({"status": "detected"})

    for segment in segments:
        video_file = segment["record_file_path"]
        cut_video_segments(str(video_file), segment, myclient)