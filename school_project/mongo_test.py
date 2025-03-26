import pymongo

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["tv"]
mycol = mydb["records"]

mydict = [{ "name": "Mathew", "address": "Highway 37" },
          { "name": "Jackob", "address": "Highway 37" }]

# x = mycol.insert_one(mydict)

myquery = {"name": "Mathew"}

mydoc = mycol.find_one(myquery)

mycol.update_one({"_id": mydoc["_id"]}, {
   "$set": {
       "address": "new address"
   } 
})

