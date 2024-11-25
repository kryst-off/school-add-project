import logging
import time
import uuid

import av


class OutputContainer:
    def __init__(self, video_stream_template, audio_stream_template):
        # Generate a unique filename for each output segment based on the timestamp and a unique identifier
        timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime())
        unique_id = uuid.uuid4().hex[:8]
        self.filename = f'scene_{timestamp}_{unique_id}.mp4'
        logging.info(f"Creating output container: {self.filename}")
        # Open the output container for writing video segments
        self.container = av.open(self.filename, mode='w', format='mp4')
        # Add video and audio streams to the output container using templates from the input streams
        self.video_stream = self.container.add_stream(template=video_stream_template)
        self.audio_stream = self.container.add_stream(template=audio_stream_template)
        # Initialize dictionaries to store bounds for PTS (Presentation Time Stamp) and DTS (Decoding Time Stamp)
        self.initial_pts = {}
        self.initial_dts = {}
        self.last_pts = {}
        self.last_dts = {}


    def adjust_pts_dts(self, packet):
        """
        Adjust the PTS (Presentation Time Stamp) and DTS (Decoding Time Stamp) of the packet.
        This ensures that the timestamps start from zero for each new segment.
        """
        input_stream = packet.stream
        # Record initial PTS and DTS if not already done for the given stream index
        if input_stream.type not in self.initial_pts:
            self.initial_pts[input_stream.type] = packet.pts
            self.initial_dts[input_stream.type] = packet.dts

        self.last_pts[input_stream.type] = packet.pts + packet.duration
        self.last_dts[input_stream.type] = packet.dts + packet.duration

        # Adjust PTS and DTS to start from zero for the new output segment
        packet.pts -= self.initial_pts[input_stream.type]
        packet.dts -= self.initial_dts[input_stream.type]


    def mux_packet(self, packet):
        # Adjust the PTS/DTS values of the packet to ensure continuity
        self.adjust_pts_dts(packet)
        # Assign the packet to the appropriate output stream (video or audio)
        output_stream = self.video_stream if packet.stream.type == 'video' else self.audio_stream
        packet.stream = output_stream
        # Write the packet to the output container
        if self.container:
            self.container.mux(packet)
        else:
            logging.error("Error: Output container is closed. Cannot mux packet.")

    def close(self):
        self.container.close()
        self.container = None
