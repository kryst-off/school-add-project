import subprocess
import logging
import av
from pathlib import Path

# Nastavení loggeru
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("video_saw")

def cut_video_segments(video_path: str, segments_file: str) -> None:
    """
    Rozřeže video na segmenty podle PTS uvedených v textovém souboru.
    Používá FFmpeg pro kopírování streamů bez překódování.
    """
    try:
        # Otevření vstupního videa pro získání time_base
        input_container = av.open(video_path)
        video_stream = input_container.streams.video[0]
        time_base = float(video_stream.time_base)
        input_container.close()

        # Načtení PTS segmentů
        segments = []
        with open(segments_file, 'r') as f:
            lines = f.readlines()
            for i in range(len(lines)-1):
                start_pts = int(lines[i].split()[1])
                end_pts = int(lines[i+1].split()[0])
                # Převod PTS na sekundy
                start_time = start_pts * time_base
                end_time = end_pts * time_base
                segments.append((start_time, end_time))
        
        # Vytvoření výstupního adresáře
        output_dir = Path(video_path).parent / "segments"
        output_dir.mkdir(exist_ok=True)
        
        # Zpracování každého segmentu
        for i, (start_time, end_time) in enumerate(segments, 1):
            output_path = output_dir / f"segment_{i:03d}.mp4"
            logger.info(f"Cutting segment {i}: {start_time:.2f}s - {end_time:.2f}s")
            
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
                logger.info(f"Segment {i} saved to {output_path}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Error cutting segment {i}: {e.stderr.decode()}")
                continue
        
        logger.info("All segments processed successfully")
        
    except Exception as e:
        logger.error(f"Error processing video: {e}")

if __name__ == "__main__":
    video_file = Path("materials") / "something" / "test_video" / "stream_20241220_235617.mp4"
    segments_file = video_file.parent / f"silent_black_segments_{video_file.stem}.txt"
    cut_video_segments(str(video_file), str(segments_file))
