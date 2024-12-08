import av
import cv2
import numpy as np
from typing import List

from .scene_detector import calculate_frame_similarity
from .segment_cutter import cut_segment
from .audio_analyzer import are_scenes_audio_similar


class VideoProcessor:
    MAX_PROCESSING_DURATION = 30  # seconds
    SCENE_CHANGE_THRESHOLD = 0.8  # If similarity is below this, check audio
    DEFINITE_SCENE_CHANGE = 0.1  # If similarity is below this, cut immediately

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
        self.audio_sample_rate = int(self.input_audio.rate)

        self.output_container = av.open(output_url, mode="w")
        self.output_video = self.output_container.add_stream(template=self.input_video)
        self.output_audio = self.output_container.add_stream(template=self.input_audio)

        # Processing state
        self.pts_shift = None
        self.started = False
        self.cut_points: List[float] = []  # List of timestamps where cuts should occur
        self.previous_frame = None

        # Add new attributes for audio analysis
        self.audio_analysis_window = 2.0  # seconds
        self.current_audio_packets = []
        self.pending_cuts = (
            []
        )  # List of (timestamp, audio_before) tuples waiting for confirmation
        self.confirmed_cuts = [0.0]  # Start with 0 as first confirmed cut

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
                    break
            elif packet.stream.type == "audio":
                self._process_audio_packet(packet)

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

            if self.previous_frame is not None:
                similarity = calculate_frame_similarity(
                    frame_array, self.previous_frame
                )
                last_cut = (
                    self.pending_cuts[-1][0]
                    if self.pending_cuts
                    else self.confirmed_cuts[-1]
                )

                if packet_time - last_cut >= self.min_scene_duration:
                    if similarity < self.DEFINITE_SCENE_CHANGE:
                        # Similarity is very low - confirm cut immediately
                        print(
                            f"Immediate scene change detected at {packet_time:.2f}s (similarity: {similarity:.3f})"
                        )
                        self.confirmed_cuts.append(packet_time)
                    elif similarity < self.SCENE_CHANGE_THRESHOLD:
                        # Store the potential cut with current audio context
                        audio_before = list(self.current_audio_packets)
                        self.pending_cuts.append((packet_time, audio_before))
                        print(
                            f"Potential scene change detected at {packet_time:.2f}s (similarity: {similarity:.3f})"
                        )

            self.previous_frame = frame_array.copy()

        if packet_time >= self.MAX_PROCESSING_DURATION:
            print(f"{self.MAX_PROCESSING_DURATION} seconds reached, stopping...")
            self._process_pending_cuts()
            if packet_time - self.confirmed_cuts[-1] >= self.min_scene_duration:
                self.confirmed_cuts.append(packet_time)
            return True
        return False

    def _process_audio_packet(self, packet):
        """Process an audio packet for scene analysis."""
        packet_time = (packet.pts - self.pts_shift) * self.time_base
        self.current_audio_packets.append(packet)

        # Remove old packets outside our analysis window
        while self.current_audio_packets:
            oldest_packet = self.current_audio_packets[0]
            oldest_time = (oldest_packet.pts - self.pts_shift) * self.time_base
            if packet_time - oldest_time > self.audio_analysis_window * 1.2:
                self.current_audio_packets.pop(0)
            else:
                break

        # Process any pending cuts that now have enough audio context
        self._process_pending_cuts()

    def _process_pending_cuts(self):
        """Process pending cuts that have enough audio context for confirmation."""
        remaining_pending_cuts = []

        for cut_time, audio_before in self.pending_cuts:
            # Get current audio packets after the potential cut
            audio_after = [
                p
                for p in self.current_audio_packets
                if (p.pts - self.pts_shift) * self.time_base > cut_time
            ]

            # Calculate the time span of audio_after
            if audio_after:
                last_packet = audio_after[-1]
                last_time = (last_packet.pts - self.pts_shift) * self.time_base
                audio_after_duration = last_time - cut_time

                # If we have enough audio context after the cut
                if audio_after_duration >= self.audio_analysis_window:
                    if not are_scenes_audio_similar(
                        audio_before, audio_after, self.audio_sample_rate
                    ):
                        print(
                            f"Scene change confirmed at {cut_time:.2f}s (audio different)"
                        )
                        self.confirmed_cuts.append(cut_time)
                    else:
                        print(
                            f"Scene change rejected at {cut_time:.2f}s (audio similar)"
                        )
                else:
                    # Keep cuts that still need more audio context
                    remaining_pending_cuts.append((cut_time, audio_before))
            else:
                # Keep cuts that have no audio after them yet
                remaining_pending_cuts.append((cut_time, audio_before))

        self.pending_cuts = remaining_pending_cuts

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
        """Process the confirmed cuts into segments."""
        print("Stream processing complete, starting cuts...")
        print(
            f"Detected {len(self.confirmed_cuts) - 1} scene changes"
        )  # -1 because first cut is at 0.0

        for i, start_time in enumerate(self.confirmed_cuts[:-1]):
            next_start = self.confirmed_cuts[i + 1]
            cut_segment(self.output_url, start_time, next_start, i + 1)

        print("All segments complete")
