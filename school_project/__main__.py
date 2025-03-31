import time
import logging
from .stream_downloader import download_stream

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

def main():
    while True:
        try:
            logger.info("Starting scheduled stream download...")
            video_file = download_stream()
            
            if video_file:
                logger.info(f"Stream successfully downloaded to: {video_file}")
            else:
                logger.error("Failed to download stream")

            # Wait 30 minutes before next download
            # logger.info("Waiting 30 minutes before next download...")
            # time.sleep(1800)  # 30 minutes in seconds
            
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            # Still wait 30 minutes before retry even if there was an error
            time.sleep(1800)

if __name__ == "__main__":
    main()
