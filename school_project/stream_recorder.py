import av
import logging
import time
import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple

# Nastavení loggeru
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stream_recorder")

# Konstanty
input_url = "http://88.212.15.27/live/nova_avc_25p/playlist.m3u8"
DURATION_LIMIT = 30  # sekundy
SCENE_CHANGE_THRESHOLD = 0.9
TEMP_DIR = Path("/tmp")

@dataclass
class SceneChange:
    timestamp: float
    pts: int

def calculate_frame_histogram(frame):
    """Calculate histogram of a frame using both grayscale and color information"""
    # Convert to grayscale for structural analysis
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Create grayscale histogram
    hist_gray = cv2.calcHist([gray], [0], None, [64], [0, 256])

    # Create 3D color histogram
    hist_color = cv2.calcHist(
        [frame], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256]
    )

    # Normalize histograms
    cv2.normalize(hist_gray, hist_gray)
    cv2.normalize(hist_color, hist_color)

    return hist_gray, hist_color

def detect_scene_change(current_frame, previous_frame, threshold=SCENE_CHANGE_THRESHOLD):
    """Detect scene change using multiple metrics"""
    if previous_frame is None:
        return False

    # 1. Histogram comparison
    hist_gray_curr, hist_color_curr = calculate_frame_histogram(current_frame)
    hist_gray_prev, hist_color_prev = calculate_frame_histogram(previous_frame)

    correl_gray = cv2.compareHist(hist_gray_curr, hist_gray_prev, cv2.HISTCMP_CORREL)
    correl_color = cv2.compareHist(hist_color_curr, hist_color_prev, cv2.HISTCMP_CORREL)

    # 2. Mean Absolute Difference (MAD)
    curr_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
    prev_gray = cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY)
    mad = np.mean(np.abs(curr_gray.astype(float) - prev_gray.astype(float)))
    mad_normalized = mad / 255.0

    # 3. Structural Similarity Index (SSIM)
    ssim = cv2.compareHist(hist_gray_curr, hist_gray_prev, cv2.HISTCMP_INTERSECT)
    ssim_normalized = ssim / np.sum(hist_gray_curr)

    # Weight the different metrics
    weights = {"correl_gray": 0.3, "correl_color": 0.3, "mad": 0.2, "ssim": 0.2}

    # Combine metrics into a single similarity score
    total_similarity = (
        weights["correl_gray"] * correl_gray
        + weights["correl_color"] * correl_color
        + weights["mad"] * (1 - mad_normalized)
        + weights["ssim"] * ssim_normalized
    )

    # Use both static and dynamic thresholds
    static_threshold = threshold
    dynamic_threshold = threshold * (1 + mad_normalized * 0.2)

    return total_similarity < min(static_threshold, dynamic_threshold)

def record_stream(input_url: str) -> Tuple[str, List[SceneChange]]:
    """Nahraje stream a detekuje změny scén"""
    scene_changes = []
    output_filename = None
    input_container = None
    output_container = None
    
    try:
        logger.info("Attempting to open input stream...")
        input_container = av.open(input_url, timeout=30)
        logger.info("Input container opened successfully")
        
        video_stream = input_container.streams.video[0]
        audio_stream = input_container.streams.audio[0]
        
        timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime())
        output_filename = f'recording_{timestamp}.mp4'
        
        output_container = av.open(output_filename, mode='w')
        output_video = output_container.add_stream(template=video_stream)
        output_audio = output_container.add_stream(template=audio_stream)
        logger.info(f"Created output file: {output_filename}")
        
        # Nastavení počátečních hodnot
        pts_offset = None
        key_frame_found = False
        prev_frame = None
        stream_timebase = float(video_stream.time_base)
        min_scene_duration = 2.0
        last_scene_time = 0
        
        # Čtení paketů
        for packet in input_container.demux(video_stream, audio_stream):
            if packet.stream.type == 'video':
                if packet.is_keyframe and not key_frame_found:
                    pts_offset = packet.pts
                    key_frame_found = True
                    logger.info(f"Found first keyframe at PTS: {pts_offset}")
                
                current_pts = packet.pts - pts_offset
                current_time = current_pts * stream_timebase
                
                if current_time > DURATION_LIMIT:
                    logger.info("Time limit reached, stopping...")
                    break
                
                # Detekce scén
                for frame in packet.decode():
                    frame_array = frame.to_ndarray(format='bgr24')
                    
                    if (detect_scene_change(frame_array, prev_frame) and 
                        key_frame_found and 
                        (current_time - last_scene_time) >= min_scene_duration):
                        logger.info(f"Scene change at {current_time:.2f}s (PTS: {current_pts})")
                        scene_changes.append(SceneChange(current_time, current_pts))
                        last_scene_time = current_time
                    
                    prev_frame = frame_array.copy()
                
                if key_frame_found:
                    packet.pts = current_pts
                    packet.dts = packet.dts - pts_offset if packet.dts is not None else None
                    packet.stream = output_video
                    output_container.mux(packet)
            
            elif packet.stream.type == 'audio' and key_frame_found:
                packet.pts -= pts_offset
                packet.dts -= pts_offset if packet.dts is not None else None
                packet.stream = output_audio
                output_container.mux(packet)
                
    except av.AVError as e:
        logger.error(f"Error recording stream: {e}")
        return None, []
    finally:
        # Bezpečné zavření kontejnerů
        if input_container:
            input_container.close()
        if output_container:
            output_container.close()
        logger.info("Recording finished")
    
    return output_filename, scene_changes

if __name__ == "__main__":
    # Přidáme více logování
    logger.info("Starting stream recording...")
    logger.info(f"Input URL: {input_url}")
    video_file, scenes = record_stream(input_url)
    logger.info(f"Recording finished. Video file: {video_file}")
    # Uložíme časové značky do souboru
    if video_file:
        markers_file = Path(video_file).with_suffix('.markers')
        with open(markers_file, 'w') as f:
            for scene in scenes:
                f.write(f"{scene.timestamp},{scene.pts}\n")
        logger.info(f"Scene markers saved to {markers_file}")