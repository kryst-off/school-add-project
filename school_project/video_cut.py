import av
import logging
import time
from pathlib import Path

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

def detect_silent_black_segments(video_path: str) -> None:
    """
    Detekuje segmenty ve videu, které jsou současně černé a tiché.
    
    Args:
        video_path: Cesta k video souboru
    """
    try:
        logger.info(f"Opening video file: {video_path}")
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
                audio_time = frame.pts * float(audio_stream.time_base)
                if old_silent != is_silent:
                    logger.info(f'Silent {is_silent} at {format_time(audio_time)}')
            
            # Stavový stroj
            if is_black and is_silent and not in_silent_black_segment:
                segment_start = video_time
                in_silent_black_segment = True
                logger.info(f"Starting silent black segment at {format_time(video_time)}")

            elif in_silent_black_segment and (not is_black or not is_silent):
                logger.info(f"Silent black segment detected: {format_time(segment_start)} - {format_time(video_time)} "
                          f"(duration: {format_time(video_time - segment_start)})")
                
                # Uložení PTS do textového souboru
                output_file = Path(video_path).parent / f"silent_black_segments_{Path(video_path).stem}.txt"
                start_pts = int(segment_start / float(video_stream.time_base))
                end_pts = int(video_time / float(video_stream.time_base))
                with open(output_file, 'a', encoding='utf-8') as f:
                    f.write(f"{start_pts} {end_pts}\n")
                    
                in_silent_black_segment = False
                segment_start = None
                
    except Exception as e:
        logger.error(f"Error processing video: {e}")
    finally:
        container.close()

if __name__ == "__main__":
    # video_file = Path("materials") / "something" / "test_video" / "stream_20241220_235617.mp4"
    video_file = Path("materials") / "something" / "test_video" / "stream_20241220_235617.mp4"
    detect_silent_black_segments(str(video_file))
