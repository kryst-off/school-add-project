import logging
import subprocess
import time
from pathlib import Path

import av

LOGGER_NAME = "StreamProcessorLogger"
SEGMENT_DURATION = 10  # Duration in seconds
OUTPUT_DIR = "output_segments"


class VideoStreamProcessor:
    def __init__(self, input_url):
        self.logger = logging.getLogger(LOGGER_NAME)
        self.input_url = input_url
        
        # Create output directory if it doesn't exist
        Path(OUTPUT_DIR).mkdir(exist_ok=True)

    def process_packets(self):
        timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime())
        
        # Use FFmpeg to segment the video directly
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', self.input_url,
            '-c', 'copy',  # Copy without re-encoding
            '-f', 'segment',  # Enable segmentation
            '-segment_time', str(SEGMENT_DURATION),  # Set segment duration
            '-reset_timestamps', '1',  # Reset timestamps for each segment
            '-movflags', '+faststart',  # Optimize for web playback
            '-y',  # Overwrite existing files
            f'{OUTPUT_DIR}/segment_{timestamp}_%03d.mp4'  # Output pattern
        ]
        
        try:
            # Run FFmpeg command
            process = subprocess.run(
                ffmpeg_cmd,
                check=True,
                capture_output=True,
                text=True
            )
            self.logger.info("Successfully created video segments")
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error creating segments: {e.stderr}")
            raise

    def close(self):
        pass
