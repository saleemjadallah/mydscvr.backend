#!/usr/bin/env python3
"""
Check current events in MongoDB to analyze duplicate filtering effectiveness
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv
from loguru import logger
from collections import Counter

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'Mongo.env'))

def analyze_current_events():
    """
    Analyze current events in the database
    """
    try:
        # Connect to MongoDB
        mongo_uri = os.getenv('Mongo_URI')
        client = MongoClient(mongo_uri, tlsAllowInvalidCertificates=True)
        db = client['DXB']
        collection = db['events']
        
        # Get current count
        total_count = collection.count_documents({})
        logger.info(f"📊 Total events in database: {total_count}")
        
        if total_count == 0:
            logger.info("ℹ️  No events in database")
            return
        
        # Analyze for potential duplicates
        events = list(collection.find({}, {
            'title': 1, 
            'venue_name': 1, 
            'start_date': 1,
            'description': 1,
            'source': 1
        }))
        
        # Check for title similarities
        titles = [event.get('title', '') for event in events]
        title_counter = Counter(titles)
        duplicates = {title: count for title, count in title_counter.items() if count > 1}
        
        logger.info(f"🔍 Potential duplicate titles: {len(duplicates)}")
        for title, count in list(duplicates.items())[:5]:
            logger.info(f"   '{title}': {count} occurrences")
        
        # Check venue distribution
        venues = [event.get('venue_name', '') for event in events]
        venue_counter = Counter(venues)
        
        logger.info(f"🏢 Top 5 venues by event count:")
        for venue, count in venue_counter.most_common(5):
            logger.info(f"   {venue}: {count} events")
        
        # Check source distribution
        sources = [event.get('source', '') for event in events]
        source_counter = Counter(sources)
        
        logger.info(f"📝 Events by source:")
        for source, count in source_counter.items():
            logger.info(f"   {source}: {count} events")
        
        # Sample recent events
        recent_events = list(collection.find({}).sort('_id', -1).limit(5))
        logger.info(f"📋 Sample of 5 most recent events:")
        for i, event in enumerate(recent_events, 1):
            logger.info(f"   {i}. {event.get('title', 'No title')} - {event.get('venue_name', 'No venue')}")
        
        client.close()
        return total_count
        
    except Exception as e:
        logger.error(f"❌ Error analyzing events: {e}")
        return 0

if __name__ == "__main__":
    logger.info("🔍 Analyzing current events in database...")
    count = analyze_current_events()
    logger.success(f"✅ Analysis completed! Total events: {count}")