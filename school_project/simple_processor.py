import av
import logging
import time
import subprocess
import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List

# Nastavení loggeru
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simple_processor")

# Konstanty
INPUT_URL = "http://88.212.15.27/live/nova_avc_25p/playlist.m3u8"
DURATION_LIMIT = 30  # sekundy
SCENE_CHANGE_THRESHOLD = 0.7  # Práh pro detekci změny scény

@dataclass
class SegmentInfo:
    start_time: float
    end_time: float
    segment_number: int

def calculate_histogram(frame):
    """Vypočítá normalizovaný histogram snímku"""
    hist = cv2.calcHist(
        [frame],
        [0, 1, 2],
        None,
        [256, 256, 256],
        [0, 256, 0, 256, 0, 256]
    )
    cv2.normalize(hist, hist)
    return hist

def is_scene_change(frame, prev_frame, threshold=SCENE_CHANGE_THRESHOLD):
    """Detekuje změnu scény porovnáním histogramů"""
    if prev_frame is None:
        return False
        
    hist_curr = calculate_histogram(frame)
    hist_prev = calculate_histogram(prev_frame)
    similarity = cv2.compareHist(hist_curr, hist_prev, cv2.HISTCMP_CORREL)
    return similarity < threshold

def cut_segment(input_file, start_time, end_time, segment_number):
    """Vyřízne segment z input souboru podle zadaných časových značek"""
    try:
        output_file = f"{Path(input_file).stem}_segment_{segment_number:03d}.mp4"
        
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-ss', str(start_time),
            '-to', str(end_time),
            '-force_key_frames', f"expr:gte(t,{start_time})",
            '-x264-params', 'keyint=1',
            '-movflags', '+faststart',
            '-y',
            output_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Successfully cut segment {segment_number} ({start_time}-{end_time}s)")
        else:
            logger.error(f"Error cutting segment: {result.stderr}")
            
    except Exception as e:
        logger.error(f"Segment cutting failed: {e}")

def process_stream(input_url):
    output_filename = None
    segments_to_cut: List[SegmentInfo] = []
    try:
        input_container = av.open(input_url)
        logger.info("Input container opened successfully")
        
        video_stream = input_container.streams.video[0]
        audio_stream = input_container.streams.audio[0]
        
        timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime())
        output_filename = f'output_{timestamp}.mp4'
        
        output_container = av.open(output_filename, mode='w')
        output_video = output_container.add_stream(template=video_stream)
        output_audio = output_container.add_stream(template=audio_stream)
        logger.info(f"Created output file: {output_filename}")
        
        # Nastavení počátečních hodnot
        pts_offset = None
        key_frame_found = False
        start_time = time.time()
        segment_start = 0
        segment_number = 1
        prev_frame = None
        
        # Čtení paketů
        for packet in input_container.demux(video_stream, audio_stream):
            current_time = time.time() - start_time
            
            # Kontrola časového limitu
            if current_time > DURATION_LIMIT:
                logger.info("Time limit reached, stopping...")
                segments_to_cut.append(SegmentInfo(
                    segment_start,
                    current_time,
                    segment_number
                ))
                break
            
            # Zpracování video paketů
            if packet.stream.type == 'video':
                # Dekódování snímku pro detekci scény
                for frame in packet.decode():
                    frame_array = frame.to_ndarray(format='bgr24')
                    
                    if is_scene_change(frame_array, prev_frame) and key_frame_found:
                        # Nalezena změna scény
                        logger.info(f"Scene change detected at {current_time}s")
                        segments_to_cut.append(SegmentInfo(
                            segment_start,
                            current_time,
                            segment_number
                        ))
                        segment_start = current_time
                        segment_number += 1
                    
                    prev_frame = frame_array.copy()
                
                if packet.is_keyframe and not key_frame_found:
                    pts_offset = packet.pts
                    key_frame_found = True
                    logger.info(f"Found first keyframe at PTS: {pts_offset}")
                
                if key_frame_found:
                    packet.pts -= pts_offset
                    packet.dts -= pts_offset
                    packet.stream = output_video
                    output_container.mux(packet)
            
            # Zpracování audio paketů
            elif packet.stream.type == 'audio' and key_frame_found:
                packet.pts -= pts_offset
                packet.dts -= pts_offset
                packet.stream = output_audio
                output_container.mux(packet)
                
    except av.AVError as e:
        logger.error(f"Error processing stream: {e}")
    finally:
        input_container.close()
        output_container.close()
        logger.info("Containers closed")
        
        # Vyřezání všech segmentů po uzavření kontejneru
        if output_filename:
            logger.info("Starting to cut segments...")
            for segment in segments_to_cut:
                cut_segment(
                    output_filename,
                    segment.start_time,
                    segment.end_time,
                    segment.segment_number
                )

if __name__ == "__main__":
    process_stream(INPUT_URL) 