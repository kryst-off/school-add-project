from datetime import datetime
from bson import ObjectId

record = {
    "_id": ObjectId("66f090909090909090909090"),
    "source": "prima_cool",
    "start_at": datetime.now(),
    "file_path": "http://ravineo-tv/prima_cool/stream_20250327_123456/stream_20250327_123456.mp4",
    "status": "downloaded", # downloaded, processed
}

segment = {
    "_id": ObjectId("66f090909090909090909091"),

    "record_id": ObjectId("66f090909090909090909090"),
    "source": "prima_cool",
    "record_file_path": "http://ravineo-tv/prima_cool/stream_20250327_123456/stream_20250327_123456.mp4",

    "start_at": datetime.now(),
    "end_at": datetime.now(),
    "start_secs": 100.5,
    "end_secs": 200.5,

    "file_path": "http://ravineo-tv/prima_cool/stream_20250327_123456/stream_20250327_123456.mp4",

    "status": "detected", # detected, extracted, confirmed, rejected
}
