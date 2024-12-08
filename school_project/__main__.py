# from school_project.video_stream_processor import VideoStreamProcessor
from school_project.video_stream_processor import VideoStreamProcessor

INPUT_URL = "http://88.212.15.27/live/nova_avc_25p/playlist.m3u8"

if __name__ == "__main__":
    # Create an instance of StreamProcessor and start processing packewdts
    processor = VideoStreamProcessor(INPUT_URL)
    processor.process_packets()
