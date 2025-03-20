import av
import logging
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List

# Nastavení loggeru
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audio_cut")

@dataclass
class SilentSegment:
    start_time: float
    end_time: float
    segment_number: int

def detect_silent_segments(video_path: str, silence_threshold: float = -50, min_silence_duration: float = 0.1) -> List[SilentSegment]:
    """Detekuje tiché segmenty ve videu"""
    silent_segments = []
    input_container = None
    output_file = Path(video_path).parent / f"silent_segments_{Path(video_path).stem}.txt"
    
    try:
        logger.info(f"Opening video file: {video_path}")
        input_container = av.open(video_path)
        
        audio_stream = input_container.streams.audio[0]
        stream_timebase = float(audio_stream.time_base)
        
        # Proměnné pro sledování tichých segmentů
        is_silent = False
        silence_start = 0
        current_segment = 1
        
        # Buffer pro RMS výpočet
        window_size = int(44100 * 0.1)  # 100ms window při 44.1kHz
        samples_buffer = []
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("Silent segments detected:\n")
            
            for frame in input_container.decode(audio=0):
                # Převod audio frame na numpy array
                samples = frame.to_ndarray()
                samples = samples.astype(np.float32)
                
                # Přidání vzorků do bufferu
                samples_buffer.extend(samples.flatten())
                
                while len(samples_buffer) >= window_size:
                    # Výpočet RMS pro aktuální okno
                    window = samples_buffer[:window_size]
                    rms = 20 * np.log10(np.sqrt(np.mean(np.square(window))) + 1e-10)
                    
                    current_time = frame.pts * stream_timebase
                    
                    # Detekce ticha
                    if rms < silence_threshold and not is_silent:
                        silence_start = current_time
                        is_silent = True
                    elif rms >= silence_threshold and is_silent:
                        silence_duration = current_time - silence_start
                        if silence_duration >= min_silence_duration:
                            segment_info = f"Segment {current_segment}: {silence_start:.2f}s - {current_time:.2f}s\n"
                            f.write(segment_info)
                            silent_segments.append(SilentSegment(
                                start_time=silence_start,
                                end_time=current_time,
                                segment_number=current_segment
                            ))
                            current_segment += 1
                        is_silent = False
                    
                    # Odstranění zpracovaných vzorků
                    samples_buffer = samples_buffer[window_size:]
                    
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
    finally:
        if input_container:
            input_container.close()
        
    logger.info(f"Results saved to: {output_file}")
    return silent_segments

if __name__ == "__main__":
    video_file = Path("materials") / "something" / "test_video" / "stream_20241220_235617.mp4"
    detect_silent_segments(video_file)
