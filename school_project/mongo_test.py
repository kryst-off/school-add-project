from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from upload_to_gcs import upload_blob
import av
import logging
import time
import pymongo
import os

# Nastavení loggeru pro lepší diagnostiku
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Připojení k MongoDB
myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["tv"]
mycol = mydb["segments"]

segments = mycol.find_one({"status": "approved"})

for segment in segments:
    if not segment:
        logger.error("No approved segments found in database")
        exit(1)

    path = Path("materials") / segments["segment_file_path"]

    # Kontrola existence souboru
    if not path.exists():
        logger.error(f"File {path} does not exist!")
        exit(1)

    logger.info(f"Starting upload of {path} to GCS bucket")

    try:
        # Zvýšení timeoutu na 600 sekund (10 minut)
        upload_blob("ravineo-tv", str(path), segments["segment_file_path"], timeout=600)
        mycol.update_one({"_id": segments["_id"]}, {"$set": {"status": "uploaded"}})
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        # Pokud chcete další diagnostické informace
        logger.exception("Detailed error information:")

    # for segment in segments:
    #     upload_blob("ravineo-tv", segment["file_path"], segment["file_path"])
