import logging

import av
import cv2

from school_project.output_container import OutputContainer
from school_project.packet_wrapper import PacketWrapper

SCENE_CHANGE_THRESHOLD = 0.7
LOGGER_NAME = "StreamProcessorLogger"


class VideoStreamProcessor:
    def __init__(self, input_url):
        self.logger = logging.getLogger(LOGGER_NAME)
        self.input_container = self.open_input_container(input_url)
        self.input_video_stream = self.input_container.streams.video[0]
        self.input_audio_stream = self.input_container.streams.audio[0]
        self.output_container = self.open_output_container()
        self.previous_frame = None

    def open_input_container(self, input_url):
        try:
            return av.open(input_url)
        except av.error.FileNotFoundError:
            self.logger.error(f"Error: Unable to open input URL: {input_url}")
            raise
        except av.AVError as e:
            self.logger.error(f"Error: AVError occurred while opening input URL: {e}")
            raise

    def open_output_container(self):
        return OutputContainer(self.input_video_stream, self.input_audio_stream)

    @staticmethod
    def calculate_normalized_histogram(frame):
        # Calculate color histogram
        hist = cv2.calcHist(
            [frame],
            [0, 1, 2],
            None,
            [256, 256, 256],
            [0, 256, 0, 256, 0, 256],
        )
        # Normalize the histogram to account for differences in lighting or contrast
        cv2.normalize(hist, hist)
        return hist

    @staticmethod
    def is_scene_change(frame, previous_frame, threshold=SCENE_CHANGE_THRESHOLD):
        """
        Detects scene change by comparing histograms of frames.
        The function calculates color histograms for both the current frame and the previous frame,
        then compares their similarity. If the similarity is below a certain threshold, a scene change is detected.
        """
        hist_frame = VideoStreamProcessor.calculate_normalized_histogram(frame)
        hist_previous_frame = VideoStreamProcessor.calculate_normalized_histogram(previous_frame)
        similarity = cv2.compareHist(hist_frame, hist_previous_frame, cv2.HISTCMP_CORREL)
        return similarity < threshold

    def process_packets(self):
        packet_buffer = []

        for packet in self.input_container.demux():
            if packet.stream.type not in ['video', 'audio']:
                continue

            if packet.stream.type == 'video':
                frames = packet.decode()
                for i, frame in enumerate(frames):
                    if frame is not None:
                        if frame.key_frame == 1:
                            # clear packet buffer
                            self.logger.info(f'Cleaning {len(packet_buffer)} buffered packets')
                            packet_buffer = []

                        frame_array = frame.to_ndarray(format='bgr24')
                        if (self.previous_frame is not None
                                # and scene_change_pending is False
                                and self.is_scene_change(frame_array, self.previous_frame)):
                            self.output_container.close()
                            self.output_container = self.open_output_container()
                            self.logger.info(f'Using {len(packet_buffer)} buffered packets')
                            for buffered_packet in packet_buffer:
                                self.output_container.mux_packet(buffered_packet)

                        self.previous_frame = frame_array

            wrapped = PacketWrapper(packet)
            self.output_container.mux_packet(wrapped)
            packet_buffer.append(wrapped)

        self.output_container.close()

    def close(self):
        self.input_container.close()
