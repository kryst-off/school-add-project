from school_project.scene_processor import process_video
# from school_project.scene_processor import process_video as process_video_with_audio

# Nejdřív rozřežeme video podle značek
video_file = "recording_20250103_184937.mp4"
process_video(video_file)

# Pak spojíme podobné scény podle zvuku
# process_video_with_audio(video_file)
