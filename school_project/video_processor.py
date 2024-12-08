import av
import cv2
import numpy as np
from typing import List

from .scene_detector import detect_scene_change
from .segment_cutter import cut_segment


class VideoProcessor:
    MAX_PROCESSING_DURATION = 30  # seconds

    def __init__(
        self, input_url: str, output_url: str, min_scene_duration: float = 1.0
    ):
        self.min_scene_duration = min_scene_duration
        self.input_url = input_url
        self.output_url = output_url

        # Container initialization
        self.input_container = av.open(input_url)
        self._print_stream_info()

        self.input_video = self.input_container.streams.video[0]
        self.input_audio = self.input_container.streams.audio[0]
        self.time_base = float(self.input_video.time_base)

        self.output_container = av.open(output_url, mode="w")
        self.output_video = self.output_container.add_stream(template=self.input_video)
        self.output_audio = self.output_container.add_stream(template=self.input_audio)

        # Processing state
        self.pts_shift = None
        self.started = False
        self.cut_points: List[float] = []  # List of timestamps where cuts should occur
        self.previous_frame = None

    def process(self):
        """Process the video and create segments."""
        try:
            self._process_video_stream()
            self._cleanup()
            self._process_cuts()
        except Exception as e:
            print(f"Error occurred: {e}")
            self._cleanup()
            raise

    def _process_video_stream(self):
        """Process video stream and detect scene changes."""
        for packet in self.input_container.demux(self.input_video, self.input_audio):
            is_started = self._handle_start(packet)
            if not is_started:
                continue

            if packet.stream.type == "video":
                should_stop = self._process_video_packet(packet)
                if should_stop:
                    break  # 30 second limit reached

            self._mux_packet(packet)

    def _handle_start(self, packet) -> bool:
        """Handle the start of video processing. Returns True if processing should continue."""
        if not self.started and packet.stream.type == "video" and packet.is_keyframe:
            print(f"Found first keyframe at PTS: {packet.pts}")
            self.pts_shift = packet.pts
            self.cut_points.append(0.0)
            self.started = True
        return self.started

    def _process_video_packet(self, packet) -> bool:
        """Process a video packet. Returns True if processing should stop."""
        packet_time = (packet.pts - self.pts_shift) * self.time_base

        for frame in packet.decode():
            frame_array = frame.to_ndarray(format="bgr24")

            if detect_scene_change(frame_array, self.previous_frame):
                if packet_time - self.cut_points[-1] >= self.min_scene_duration:
                    print(f"Scene change detected at {packet_time:.2f}s")
                    self.cut_points.append(packet_time)

            self.previous_frame = frame_array.copy()

        if packet_time >= 30:
            print("30 seconds reached, stopping...")
            if packet_time - self.cut_points[-1] >= self.min_scene_duration:
                self.cut_points.append(packet_time)
            return True
        return False

    def _mux_packet(self, packet):
        """Mux a packet to the output container."""
        packet.stream = (
            self.output_video if packet.stream.type == "video" else self.output_audio
        )
        packet.pts -= self.pts_shift
        packet.dts -= self.pts_shift
        self.output_container.mux(packet)

    def _print_stream_info(self):
        print("Video Stream:")
        for stream in self.input_container.streams.video:
            print(f"- Codec: {stream.codec_context.name}")
            print(f"- Format: {stream.format}")
            print(f"- Bit Rate: {stream.bit_rate}")
            print(f"- Resolution: {stream.width}x{stream.height}")
            print(f"- Framerate: {stream.average_rate}")

        print("\nAudio Stream:")
        for stream in self.input_container.streams.audio:
            print(f"- Codec: {stream.codec_context.name}")
            print(f"- Format: {stream.format}")
            print(f"- Bit Rate: {stream.bit_rate}")
            print(f"- Sample Rate: {stream.rate}")
            print(f"- Channels: {stream.channels}")

    def _cleanup(self):
        self.input_container.close()
        self.output_container.close()

    def _process_cuts(self):
        print("Stream processing complete, starting cuts...")
        print(f"Detected {len(self.cut_points)} scene changes")

        for i, start_time in enumerate(self.cut_points[:-1]):
            next_start = self.cut_points[i + 1]
            cut_segment(self.output_url, start_time, next_start, i + 1)

        print("All segments complete")
