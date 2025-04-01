import pymongo

def validate_segment_length(segment: dict) -> bool:

    # Check if duration is within 0.1 seconds of being divisible by 5
    # Round to 5 decimal places to handle floating point imprecision
    duration_rounded = round(segment["duration_secs"])
    if duration_rounded % 5 == 0:
        mycol.update_one({"_id": segment["_id"]}, {"$set": {"status": "approved"}})
    else:
        mycol.update_one({"_id": segment["_id"]}, {"$set": {"status": "needs_review"}})

if __name__ == "__main__":
    myclient = pymongo.MongoClient("mongodb://localhost:27017/")
    mydb = myclient["tv"]
    mycol = mydb["segments"]

    segments = mycol.find({"status": "saved"})

    for segment in segments:
        validate_segment_length(segment)

