import subprocess


def cut_segment(
    input_file: str, start_time: float, end_time: float, segment_index: int
):
    """Cut a segment of video between two time points using ffmpeg."""
    output_file = f"output_{segment_index:03d}.mp4"

    cmd = [
        "ffmpeg",
        "-accurate_seek",
        "-i",
        input_file,
        "-ss",
        str(start_time),
        "-to",
        str(end_time),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-start_at_zero",
        "-y",
        output_file,
    ]

    print(f"Cutting segment {segment_index} from {start_time:.2f}s to {end_time:.2f}s")
    process = subprocess.run(cmd, capture_output=True)
    print(f"Segment {segment_index} done: {output_file}")
