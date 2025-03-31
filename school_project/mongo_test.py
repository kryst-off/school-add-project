import pymongo

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["tv"]
mycol = mydb["records"]

myquery = {"status": "detected"}

mydoc = mycol.find(myquery)

for x in mydoc:
    print(x)
    mycol.update_one({"_id": x["_id"]}, {
    "$set": {"status": "downloaded"}
    })

