import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# MongoDB Atlas Connection URI
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGO_DB", "trace_db")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[MONGO_DB]

def get_db():
    """Returns MongoDB database instance."""
    return db

def check_health():
    """Quick ping to check database connectivity."""
    try:
        client.admin.command('ping')
        return {"status": "connected", "database": MONGO_DB}
    except Exception as e:
        return {"status": "error", "message": str(e)}
