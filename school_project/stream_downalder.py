from pathlib import Path
from datetime import datetime
import av
import logging
import time
import pymongo

# Nastavení loggeru
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stream_downald")

# Konstanty
INPUT_URL = "https://prima-ott-live-sec.ssl.cdn.cra.cz/ZjmQ8eE2TiF8Yu1CmQeY7A==,1743109987/channels/prima_cool/playlist-live_lq.m3u8"
DURATION_LIMIT = 1800  # sekundy

def download_stream(input_url: str = INPUT_URL) -> str:
    """Stáhne stream a uloží ho do souboru v adresáři materials/nova/stream_name"""
    output_filename = None
    input_container = None
    output_container = None
    
    try:
        # Vytvoření cesty pro výstupní soubor v materials
        materials_dir = Path("materials")
        if not materials_dir.exists():
            materials_dir.mkdir()
            logger.info("Created materials directory")
            
        # Vytvoření cesty pro výstupní soubor v nova
        primacool_dir = materials_dir / "prima_cool"
        if not primacool_dir.exists():
            primacool_dir.mkdir()
            logger.info("Created nova directory")
        
        # Vytvoření adresáře podle názvu streamu
        recorddate = datetime.now()
        timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime())
        stream_dir = primacool_dir / f"stream_{timestamp}"
        if not stream_dir.exists():
            stream_dir.mkdir()
            logger.info(f"Created stream directory: {stream_dir}")
        
        logger.info("Attempting to open input stream...")
        input_container = av.open(input_url, timeout=30)
        logger.info("Input container opened successfully")
        
        video_stream = input_container.streams.video[0]
        audio_stream = input_container.streams.audio[0]
        
        output_filename = stream_dir / f'recording_{timestamp}.mp4'
        
        output_container = av.open(str(output_filename), mode='w')
        output_video = output_container.add_stream(template=video_stream)
        output_audio = output_container.add_stream(template=audio_stream)
        logger.info(f"Created output file: {output_filename}")
        
        # Nastavení počátečních hodnot
        pts_offset = None
        key_frame_found = False
        stream_timebase = float(video_stream.time_base)
        
        # Čtení paketů
        for packet in input_container.demux(video_stream, audio_stream):
            if packet.stream.type == 'video':
                if packet.is_keyframe and not key_frame_found:
                    pts_offset = packet.pts
                    key_frame_found = True
                    logger.info(f"Found first keyframe at PTS: {pts_offset}")
                
                current_pts = packet.pts - pts_offset
                current_time = current_pts * stream_timebase
                
                if current_time > DURATION_LIMIT:
                    logger.info("Time limit reached, stopping...")
                    break
                
                if key_frame_found:
                    packet.pts -= pts_offset
                    packet.dts -= pts_offset if packet.dts is not None else None
                    packet.stream = output_video
                    output_container.mux(packet)
            
            elif packet.stream.type == 'audio' and key_frame_found:
                packet.pts -= pts_offset
                packet.dts -= pts_offset if packet.dts is not None else None
                packet.stream = output_audio
                output_container.mux(packet)
                
    except av.AVError as e:
        logger.error(f"Error downloading stream: {e}")
        return None
    finally:
        # Bezpečné zavření kontejnerů
        if input_container:
            input_container.close()
        if output_container:
            output_container.close()
        logger.info("Download finished")

    myclient = pymongo.MongoClient("mongodb://localhost:27017/")
    mydb = myclient["tv"]
    mycol = mydb["records"]
    record = {
        "name": str(output_filename.name),
        "status": "downloaded",
        "source": INPUT_URL,
        "date": recorddate
    }
    mycol.insert_one(record)
    logger.info(f"Added record to database: {record}")

    return str(output_filename)


if __name__ == "__main__":
    logger.info("Starting stream download...")
    logger.info(f"Input URL: {INPUT_URL}")
    logger.info(f"Duration limit: {DURATION_LIMIT} seconds")
    
    video_file = download_stream()
    if video_file:
        logger.info(f"Stream successfully downloaded to: {video_file}")
    else:
        logger.error("Failed to download stream")
