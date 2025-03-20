import av
import logging
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List

# Nastavení loggeru
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("detection")

def analyze_video_frame(frame: av.VideoFrame, threshold: float = 0.02) -> bool:
    """
    Analyzuje jeden video frame a vrací True pokud je černý.
    
    Args:
        frame: av.VideoFrame instance
        threshold: práh pro detekci černé (0-1)
    
    Returns:
        bool: True pokud je frame černý, jinak False
    """
    try:
        frame_array = frame.to_ndarray(format='gray')
        mean_value = np.mean(frame_array)
        return mean_value < threshold * 255
    except Exception as e:
        logger.error(f"Chyba při analýze video framu: {e}")
        return False

@dataclass
class SilenceDetector:
    """
    Třída pro detekci ticha v audio framech s udržováním bufferu.
    Používá hysterezi pro stabilnější detekci - má rozdílné prahy pro aktivaci a deaktivaci ticha.
    """
    activation_threshold: float = -50    # Práh pro aktivaci ticha (nižší hodnota)
    deactivation_threshold: float = -45  # Práh pro deaktivaci ticha (vyšší hodnota)
    sample_rate: int = 44100
    window_size: int = None
    
    def __post_init__(self):
        if self.window_size is None:
            # 100ms window při daném sample rate
            self.window_size = int(self.sample_rate * 0.2)
        self.samples_buffer = []
        self.is_silent = False

    def analyze_frame(self, frame: av.AudioFrame) -> bool:
        """
        Analyzuje jeden audio frame a vrací True pokud je tichý.
        Používá hysterezi pro stabilnější detekci ticha.
        
        Args:
            frame: av.AudioFrame instance
        
        Returns:
            bool: True pokud je frame tichý, jinak False
        """
        try:
            samples = frame.to_ndarray().astype(np.float32)
            self.samples_buffer.extend(samples.flatten())

            # Analyzujeme pouze pokud máme dostatek vzorků
            if len(self.samples_buffer) >= self.window_size:
                self.samples_buffer = self.samples_buffer[-self.window_size:]
                rms = 20 * np.log10(np.sqrt(np.mean(np.square(self.samples_buffer))) + 1e-10)
                
                # Aplikujeme hysterezi
                if not self.is_silent and rms < self.activation_threshold:
                    self.is_silent = True
                elif self.is_silent and rms > self.deactivation_threshold:
                    self.is_silent = False                
            
            return self.is_silent
            
        except Exception as e:
            logger.error(f"Chyba při analýze audio framu: {e}")
            return False

    def reset_buffer(self):
        """Vyčistí buffer vzorků a resetuje stav."""
        self.samples_buffer = []
        self.is_silent = False
