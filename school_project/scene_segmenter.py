import logging
import subprocess
from pathlib import Path
import time
import av
import cv2
import numpy as np

LOGGER_NAME = "SceneSegmenterLogger"
SCENE_CHANGE_THRESHOLD = 0.7
OUTPUT_DIR = "scene_segments"


class SceneSegmenter:
    def __init__(self, input_segments_dir="output_segments"):
        self.logger = logging.getLogger(LOGGER_NAME)
        self.input_dir = Path(input_segments_dir)
        self.output_dir = Path(OUTPUT_DIR)
        self.output_dir.mkdir(exist_ok=True)
        self.scene_changes = []
        self.current_segment = None
        self.previous_frame = None

    @staticmethod
    def calculate_normalized_histogram(frame):
        hist = cv2.calcHist(
            [frame],
            [0, 1, 2],
            None,
            [256, 256, 256],
            [0, 256, 0, 256, 0, 256],
        )
        cv2.normalize(hist, hist)
        return hist

    @staticmethod
    def is_scene_change(frame, previous_frame, threshold=SCENE_CHANGE_THRESHOLD):
        hist_frame = SceneSegmenter.calculate_normalized_histogram(frame)
        hist_previous_frame = SceneSegmenter.calculate_normalized_histogram(previous_frame)
        similarity = cv2.compareHist(hist_frame, hist_previous_frame, cv2.HISTCMP_CORREL)
        return similarity < threshold

    def create_scene_segment(self, start_file, start_time, end_file, end_time):
        timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime())
        output_file = self.output_dir / f'scene_{timestamp}.mp4'

        # Create a concat file for FFmpeg
        concat_file = self.output_dir / 'concat.txt'
        with open(concat_file, 'w') as f:
            current_file = start_file
            while current_file <= end_file:
                f.write(f"file '{current_file.absolute()}'\n")
                current_file = self.get_next_segment(current_file)
                if current_file is None:
                    break

        # Use FFmpeg to create the scene segment
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),
            '-ss', str(start_time),
            '-to', str(end_time),
            '-c', 'copy',
            '-movflags', '+faststart',
            '-y',
            str(output_file)
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            self.logger.info(f"Created scene segment: {output_file}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error creating scene segment: {e}")
        finally:
            concat_file.unlink(missing_ok=True)

    def get_next_segment(self, current_file):
        """Get the next segment file in sequence"""
        segments = sorted(self.input_dir.glob('*.mp4'))
        try:
            current_index = segments.index(current_file)
            if current_index + 1 < len(segments):
                return segments[current_index + 1]
        except ValueError:
            pass
        return None

    def process_segments(self):
        segments = sorted(self.input_dir.glob('*.mp4'))
        if not segments:
            self.logger.error("No input segments found")
            return

        scene_start_file = segments[0]
        scene_start_time = 0
        current_time = 0

        for segment_file in segments:
            try:
                container = av.open(str(segment_file))
                stream = container.streams.video[0]

                for frame in container.decode(video=0):
                    frame_array = frame.to_ndarray(format='bgr24')
                    frame_time = frame.pts * frame.time_base

                    if self.previous_frame is not None:
                        if self.is_scene_change(frame_array, self.previous_frame):
                            # Create segment from scene_start to current position
                            self.create_scene_segment(
                                scene_start_file,
                                scene_start_time,
                                segment_file,
                                current_time + frame_time
                            )
                            # Start new scene
                            scene_start_file = segment_file
                            scene_start_time = frame_time

                    self.previous_frame = frame_array.copy()
                
                current_time += float(stream.duration * stream.time_base)
                container.close()

            except Exception as e:
                self.logger.error(f"Error processing segment {segment_file}: {e}")

        # Create final segment if needed
        if scene_start_file != segments[-1] or scene_start_time > 0:
            self.create_scene_segment(
                scene_start_file,
                scene_start_time,
                segments[-1],
                current_time
            )


def main():
    logging.basicConfig(level=logging.INFO)
    segmenter = SceneSegmenter()
    segmenter.process_segments()


if __name__ == "__main__":
    main() 