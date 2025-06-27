#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pymongo import MongoClient
from config import settings

def test_mongodb_connection():
    print(f"Testing MongoDB connection...")
    print(f"MongoDB URL: {settings.mongodb_url}")
    print(f"MongoDB Database: {settings.mongodb_database}")
    
    try:
        # Test connection
        client = MongoClient(settings.mongodb_url, serverSelectionTimeoutMS=5000)
        
        # Test if we can list databases
        db_list = client.list_database_names()
        print(f"✅ Connection successful! Found {len(db_list)} databases")
        
        # Test specific database
        db = client[settings.mongodb_database]
        collections = db.list_collection_names()
        print(f"✅ Database '{settings.mongodb_database}' has {len(collections)} collections")
        
        # Check if event_advice collection exists
        if 'event_advice' in collections:
            print("✅ 'event_advice' collection exists")
            count = db.event_advice.count_documents({})
            print(f"   Collection has {count} documents")
        else:
            print("❌ 'event_advice' collection does not exist")
            
        # Check if events collection exists
        if 'events' in collections:
            print("✅ 'events' collection exists")
            count = db.events.count_documents({})
            print(f"   Collection has {count} documents")
        else:
            print("❌ 'events' collection does not exist")
            
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ MongoDB connection error: {e}")
        print(f"Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    test_mongodb_connection()