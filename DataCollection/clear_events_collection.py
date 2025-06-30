#!/usr/bin/env python3
"""
Script to clear all events from MongoDB DXB.events collection
"""

import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
from loguru import logger

# Load environment variables from both files
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'AI_API.env'))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'Mongo.env'))

def clear_events_collection():
    """
    Delete all events from the MongoDB DXB.events collection
    """
    try:
        # Get MongoDB connection string
        mongo_uri = os.getenv('Mongo_URI') or os.getenv('MONGODB_URI')
        if not mongo_uri:
            logger.error("❌ Mongo_URI not found in environment variables")
            return False
        
        # Connect to MongoDB with SSL settings
        logger.info("🔗 Connecting to MongoDB...")
        client = MongoClient(mongo_uri, tlsAllowInvalidCertificates=True)
        db = client['DXB']
        collection = db['events']
        
        # Check current count
        current_count = collection.count_documents({})
        logger.info(f"📊 Current events count: {current_count}")
        
        if current_count == 0:
            logger.info("✅ Collection is already empty")
            return True
        
        # Confirm deletion
        logger.warning(f"⚠️  About to delete {current_count} events from DXB.events collection")
        
        # Delete all documents
        result = collection.delete_many({})
        
        # Verify deletion
        new_count = collection.count_documents({})
        
        logger.info(f"✅ Successfully deleted {result.deleted_count} events")
        logger.info(f"📊 New events count: {new_count}")
        
        if new_count == 0:
            logger.success("🎉 Collection successfully cleared!")
            return True
        else:
            logger.error(f"❌ Some events remain: {new_count}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error clearing collection: {e}")
        return False
    finally:
        try:
            client.close()
            logger.info("🔌 MongoDB connection closed")
        except:
            pass

if __name__ == "__main__":
    logger.info("🚀 Starting MongoDB events collection cleanup...")
    success = clear_events_collection()
    
    if success:
        logger.success("✅ Collection cleared successfully!")
        sys.exit(0)
    else:
        logger.error("❌ Failed to clear collection")
        sys.exit(1)