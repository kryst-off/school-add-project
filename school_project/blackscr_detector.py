import av
import logging
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List

# Nastavení loggeru
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("black_detector")

@dataclass
class BlackSegment:
    start_time: float
    end_time: float
    start_pts: int
    end_pts: int

def detect_black_segments(video_path: str, threshold: float = 0.02) -> bool:
    """Detekuje černé segmenty ve videu. Vrací True pokud našel alespoň jeden segment."""
    found_segment = False
    input_container = None
    
    try:
        logger.info(f"Opening video file: {video_path}")
        input_container = av.open(video_path)
        
        video_stream = input_container.streams.video[0]
        stream_timebase = float(video_stream.time_base)
        
        # Proměnné pro sledování černých segmentů
        is_black = False
        black_start_time = 0
        black_start_pts = 0
        
        for frame in input_container.decode(video=0):
            # Převod přímo do grayscale formátu
            frame_array = frame.to_ndarray(format='gray')
            current_time = frame.pts * stream_timebase
            
            mean_value = np.mean(frame_array)
            
            # Detekce černého snímku
            if mean_value < threshold * 255:
                if not is_black:
                    black_start_time = current_time
                    black_start_pts = frame.pts
                    is_black = True
            else:
                if is_black:
                    found_segment = True
                    logger.info(f"Black segment detected: {black_start_time:.2f}s - {current_time:.2f}s")
                    is_black = False
                
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        return False
    finally:
        if input_container:
            input_container.close()
    
    return found_segment

if __name__ == "__main__":
    video_file = Path("materials") / "something" / "test_video" / "stream_20241220_235617.mp4"
    output_file = video_file.parent / f"black_segments_{video_file.stem}.txt"
    
    logger.info("Starting black segment detection...")
    found_segment = detect_black_segments(str(video_file))
    
    with open(output_file, "w") as f:
        f.write("Black segments detected:\n")
        if found_segment:
            f.write("Segment found\n")
        else:
            f.write("No black segments detected\n")
    
    logger.info(f"Results written to {output_file}")
