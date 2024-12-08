from school_project.video_processor import VideoProcessor

INPUT_URL = "http://88.212.15.27/live/nova_avc_25p/playlist.m3u8"
OUTPUT_URL = "output_test.mp4"

if __name__ == "__main__":
    processor = VideoProcessor(INPUT_URL, OUTPUT_URL)
    processor.process()
