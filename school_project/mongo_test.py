import pymongo

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["tv"]
mycol = mydb["records"]
mycol2 = mydb["segments"]

myquery = {"source": "prima_cool"}

mydoc = mycol.find(myquery)



