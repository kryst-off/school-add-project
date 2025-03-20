import av
import logging
from pathlib import Path

# Nastavení loggeru
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("video_saw")

def cut_video_segments(video_path: str, segments_file: str) -> None:
    """
    Rozřeže video na segmenty podle PTS uvedených v textovém souboru.
    
    Args:
        video_path: Cesta k video souboru
        segments_file: Cesta k souboru s PTS segmentů
    """
    try:
        # Otevření vstupního videa pro získání time_base
        input_container = av.open(video_path)
        video_stream = input_container.streams.video[0]
        audio_stream = input_container.streams.audio[0]
        time_base = float(video_stream.time_base)

        # Načtení PTS segmentů
        segments = []
        with open(segments_file, 'r') as f:
            lines = f.readlines()
            for i in range(len(lines)-1):
                start_pts = int(lines[i].split()[1])  # Konec současného černého segmentu
                end_pts = int(lines[i+1].split()[0])  # Začátek dalšího černého segmentu
                segments.append((start_pts, end_pts))
        
        # Vytvoření výstupního adresáře
        output_dir = Path(video_path).parent / "segments"
        output_dir.mkdir(exist_ok=True)
        
        # Zpracování každého segmentu
        for i, (start_pts, end_pts) in enumerate(segments, 1):
            output_path = output_dir / f"segment_{i:03d}.mp4"
            logger.info(f"Cutting segment {i}: PTS {start_pts} - {end_pts}")
            
            # Vytvoření výstupního kontejneru
            output_container = av.open(str(output_path), mode='w')
            output_video = output_container.add_stream(template=video_stream)
            output_audio = output_container.add_stream(template=audio_stream)
            
            # Nastavení pozice podle PTS
            input_container.seek(start_pts)
            
            for packet in input_container.demux(video_stream, audio_stream):
                if packet.dts is None:
                    continue
                    
                if packet.dts < start_pts:
                    continue
                if packet.dts > end_pts:
                    break
                    
                # Úprava časových značek
                packet.dts -= start_pts
                if packet.pts is not None:
                    packet.pts -= start_pts
                    
                # Přiřazení správného výstupního streamu
                if packet.stream.type == 'video':
                    packet.stream = output_video
                else:
                    packet.stream = output_audio
                    
                output_container.mux(packet)
            
            output_container.close()
            logger.info(f"Segment {i} saved to {output_path}")
            
        input_container.close()
        logger.info("All segments processed successfully")
        
    except Exception as e:
        logger.error(f"Error processing video: {e}")

if __name__ == "__main__":
    video_file = Path("materials") / "something" / "test_video" / "stream_20241220_235617.mp4"
    segments_file = video_file.parent / f"silent_black_segments_{video_file.stem}.txt"
    cut_video_segments(str(video_file), str(segments_file))
