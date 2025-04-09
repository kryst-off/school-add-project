from google.cloud import storage
from pathlib import Path
import os
import logging
import pymongo


def upload_blob(bucket_name, source_file_name, destination_blob_name, timeout=300):


    
    """Uploads a file to the bucket."""
    # The ID of your GCS bucket
    # bucket_name = "your-bucket-name"
    # The path to your file to upload
    # source_file_name = "local/path/to/file"
    # The ID of your GCS object
    # destination_blob_name = "storage-object-name"

    # Print file size for debugging
    file_size = os.path.getsize(source_file_name)
    print(f"Uploading file {source_file_name} ({file_size} bytes) to {destination_blob_name}")

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    # Optional: set a generation-match precondition to avoid potential race conditions
    # and data corruptions. The request to upload is aborted if the object's
    # generation number does not match your precondition. For a destination
    # object that does not yet exist, set the if_generation_match precondition to 0.
    # If the destination object already exists in your bucket, set instead a
    # generation-match precondition using its generation number.
    generation_match_precondition = 0

    # Set timeout for upload
    blob.upload_from_filename(
        source_file_name, 
        if_generation_match=generation_match_precondition,
        timeout=timeout
    )

    print(
        f"File {source_file_name} uploaded to {destination_blob_name}."
    )

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
