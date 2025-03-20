import logging
import time
import subprocess
import cv2
import numpy as np
import librosa
from pathlib import Path
from dataclasses import dataclass
from typing import List

# Nastavení loggeru
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scene_processor")

# Konstanty
AUDIO_SIMILARITY_THRESHOLD = 0.2
TEMP_DIR = Path("/tmp")


@dataclass
class SceneInfo:
    start_time: float
    end_time: float
    segment_number: int
    audio_fingerprint: np.ndarray = None

def load_scene_markers(markers_file: Path) -> List[float]:
    """Načte časové značky scén ze souboru"""
    timestamps = []
    try:
        with open(markers_file) as f:
            for line in f:
                timestamp, _ = line.strip().split(',')
                timestamps.append(float(timestamp))
        logger.info(f"Loaded {len(timestamps)} scene markers from {markers_file.name}")
        for i, ts in enumerate(timestamps, 1):
            logger.info(f"  Scene {i} starts at: {ts:.2f}s")
        return timestamps
    except Exception as e:
        logger.error(f"Error loading markers from {markers_file}: {e}")
        return []

def extract_audio_features(input_file, start_time, end_time):
    """Extrahuje zvukové charakteristiky ze segmentu"""
    try:
        # Dočasný soubor pro audio
        temp_audio = str(TEMP_DIR / f"temp_audio_{int(time.time())}.wav")
        
        # Extrahujeme audio pomocí FFmpeg
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-ss', str(start_time),
            '-to', str(end_time),
            '-ac', '1',  # Mono
            '-ar', '22050',  # Sample rate
            '-y',
            temp_audio
        ]
        
        subprocess.run(cmd, capture_output=True)
        
        # Načteme audio
        y, sr = librosa.load(temp_audio, sr=22050)
        
        if len(y) == 0:  # Kontrola prázdného audio
            logger.warning("Empty audio segment")
            return None
            
        # Vypočítáme různé charakteristiky
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        zero_crossing_rate = librosa.feature.zero_crossing_rate(y)
        
        # Zajistíme, že všechny charakteristiky mají správný tvar
        mfcc_mean = np.mean(mfcc, axis=1)
        centroid_mean = np.mean(spectral_centroid)
        rolloff_mean = np.mean(spectral_rolloff)
        zcr_mean = np.mean(zero_crossing_rate)
        
        # Vytvoříme vektor charakteristik se správnými dimenzemi
        features = np.concatenate([
            mfcc_mean,
            np.array([centroid_mean]),
            np.array([rolloff_mean]),
            np.array([zcr_mean])
        ])
        
        # Uklidíme dočasný soubor
        Path(temp_audio).unlink()
        
        return features
        
    except Exception as e:
        logger.error(f"Error extracting audio features: {e}")
        return None

def are_scenes_similar(scene1: SceneInfo, scene2: SceneInfo, threshold=AUDIO_SIMILARITY_THRESHOLD):
    """Porovná dvě scény na základě jejich zvukových charakteristik"""
    if scene1.audio_fingerprint is None or scene2.audio_fingerprint is None:
        return False
    
    try:
        # Rozdělíme features na jednotlivé komponenty
        mfcc1, spec1 = scene1.audio_fingerprint[:13], scene1.audio_fingerprint[13:]
        mfcc2, spec2 = scene2.audio_fingerprint[:13], scene2.audio_fingerprint[13:]
        
        # Vypočítáme podobnost pro různé charakteristiky
        mfcc_similarity = np.dot(mfcc1, mfcc2) / (np.linalg.norm(mfcc1) * np.linalg.norm(mfcc2))
        spec_similarity = np.dot(spec1, spec2) / (np.linalg.norm(spec1) * np.linalg.norm(spec2))
        
        # Vážený průměr podobností
        total_similarity = 0.7 * mfcc_similarity + 0.3 * spec_similarity
        
        # Přidáme toleranci pro délku scén
        duration1 = scene1.end_time - scene1.start_time
        duration2 = scene2.end_time - scene2.start_time
        duration_ratio = min(duration1, duration2) / max(duration1, duration2)
        
        # Pokud jsou scény příliš rozdílné délky, snížíme podobnost
        if duration_ratio < 0.5:  # Pokud je jedna scéna 2x delší než druhá
            total_similarity *= duration_ratio
        
        logger.debug(f"Similarity between scenes {scene1.segment_number} and {scene2.segment_number}: {total_similarity:.3f}")
        return total_similarity > threshold
        
    except Exception as e:
        logger.error(f"Error comparing scenes: {e}")
        return False

def merge_similar_scenes(scenes: List[SceneInfo], input_file) -> List[SceneInfo]:
    """Sloučí sousední scény s podobnou zvukovou stopou"""
    if not scenes:
        return []
    
    # Extrahujeme zvukové charakteristiky pro každou scénu
    for scene in scenes:
        scene.audio_fingerprint = extract_audio_features(
            input_file,
            scene.start_time,
            scene.end_time
        )
    
    # Procházíme scény postupně a spojujeme podobné sousední
    merged_scenes = []
    current_scene = scenes[0]
    
    for next_scene in scenes[1:]:
        if are_scenes_similar(current_scene, next_scene):
            # Sloučíme scény
            logger.info(f"Merging scenes {current_scene.segment_number} and {next_scene.segment_number}")
            current_scene.end_time = next_scene.end_time
            # Aktualizujeme audio fingerprint pro sloučenou scénu
            current_scene.audio_fingerprint = extract_audio_features(
                input_file,
                current_scene.start_time,
                current_scene.end_time
            )
        else:
            # Přidáme aktuální scénu a začneme novou
            merged_scenes.append(current_scene)
            current_scene = next_scene
    
    # Přidáme poslední scénu
    merged_scenes.append(current_scene)
    
    # Přečíslujeme scény
    for i, scene in enumerate(merged_scenes, 1):
        scene.segment_number = i
        logger.info(f"Final scene {i}: {scene.start_time:.2f}s - {scene.end_time:.2f}s")
    
    return merged_scenes

def cut_segment(input_file, start_time, end_time, segment_number):
    """Vyřízne segment z input souboru podle zadaných časových značek"""
    try:
        # Vytvoříme adresář pro scény
        input_path = Path(input_file)
        scenes_dir = input_path.parent / f"scenes_{input_path.stem}"
        scenes_dir.mkdir(exist_ok=True)
        
        # Vytvoříme název výstupního souboru
        output_file = scenes_dir / f"scene_{input_path.stem}_{segment_number:03d}.mp4"
        
        logger.info(f"Cutting scene {segment_number}:")
        logger.info(f"  Input: {input_path.name}")
        logger.info(f"  Output: {output_file}")
        logger.info(f"  Time range: {start_time:.2f}s - {end_time:.2f}s")
        logger.info(f"  Duration: {end_time - start_time:.2f}s")
        
        cmd = [
            'ffmpeg',
            '-i', str(input_file),  # Převedeme na string pro jistotu
            '-ss', str(start_time),
            '-to', str(end_time),
            '-force_key_frames', f"expr:gte(t,{start_time})",
            '-x264-params', 'keyint=1',
            '-movflags', '+faststart',
            '-y',
            str(output_file)  # Převedeme na string pro jistotu
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"  Successfully saved: {output_file.name}")
        else:
            logger.error(f"  Error cutting scene: {result.stderr}")
            
    except Exception as e:
        logger.error(f"  Failed to cut scene {segment_number}: {e}")

def process_video(video_file: str):
    """Zpracuje nahrané video a rozdělí ho na scény"""
    video_path = Path(video_file)
    markers_file = video_path.with_suffix('.markers')
    
    logger.info(f"Processing video file: {video_path.name}")
    
    if not video_path.exists():
        logger.error("Video file not found")
        return
        
    if not markers_file.exists():
        logger.error("Markers file not found")
        return

    # Načteme časové značky
    timestamps = load_scene_markers(markers_file)
    if not timestamps:
        return

    # 1. Nejdřív vyřežeme scény podle časových značek
    scenes_by_time_dir = video_path.parent / f"scenes_by_time_{video_path.stem}"
    scenes_by_time_dir.mkdir(exist_ok=True)
    
    logger.info("Cutting scenes by time markers...")
    for i in range(len(timestamps)):
        start_time = timestamps[i]
        end_time = timestamps[i + 1] if i < len(timestamps) - 1 else None
        
        if end_time is None:
            logger.info(f"  Skipping last scene marker at {start_time:.2f}s")
            continue
            
        # Vyřežeme scénu podle časových značek
        output_file = scenes_by_time_dir / f"scene_{video_path.stem}_{i+1:03d}.mp4"
        
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-ss', str(start_time),
            '-to', str(end_time),
            '-c', 'copy',
            '-movflags', '+faststart',
            '-y',
            str(output_file)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"  Cut scene {i+1}: {start_time:.2f}s - {end_time:.2f}s")
        else:
            logger.error(f"  Error cutting scene {i+1}: {result.stderr}")

    # 2. Pak vytvoříme SceneInfo objekty pro zvukovou analýzu
    scenes = []
    logger.info("\nCreating scene objects for audio analysis...")
    for i in range(len(timestamps)):
        start_time = timestamps[i]
        end_time = timestamps[i + 1] if i < len(timestamps) - 1 else None

        if end_time is None:
            continue

        scenes.append(SceneInfo(
            start_time=start_time,
            end_time=end_time,
            segment_number=i + 1
        ))
        logger.info(f"  Scene {i+1}: {start_time:.2f}s - {end_time:.2f}s")

    # 3. Sloučíme podobné scény podle zvuku
    merged_scenes = merge_similar_scenes(scenes, video_file)

    # 4. Vyřežeme finální scény podle zvukové analýzy
    scenes_by_audio_dir = video_path.parent / f"scenes_by_audio_{video_path.stem}"
    scenes_by_audio_dir.mkdir(exist_ok=True)
    
    logger.info(f"\nCutting {len(merged_scenes)} scenes based on audio analysis...")
    for scene in merged_scenes:
        output_file = scenes_by_audio_dir / f"scene_{video_path.stem}_{scene.segment_number:03d}.mp4"
        
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-ss', str(scene.start_time),
            '-to', str(scene.end_time),
            '-c', 'copy',
            '-movflags', '+faststart',
            '-y',
            str(output_file)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"  Cut scene {scene.segment_number}: {scene.start_time:.2f}s - {scene.end_time:.2f}s")
        else:
            logger.error(f"  Error cutting scene {scene.segment_number}: {result.stderr}")
    
    logger.info("\nVideo processing completed")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python scene_processor.py <video_file>")
        sys.exit(1)

    process_video(sys.argv[1])