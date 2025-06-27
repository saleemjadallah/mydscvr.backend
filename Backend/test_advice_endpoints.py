#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from main import app
from pymongo import MongoClient
from config import settings

def test_advice_endpoints():
    client = TestClient(app)
    
    print("Testing advice endpoints...")
    
    # Test 1: GET /api/advice/event/{event_id}
    print("\n1. Testing GET /api/advice/event/{event_id}")
    
    # First get a valid event ID
    mongo_client = MongoClient(settings.mongodb_url)
    db = mongo_client[settings.mongodb_database]
    event = db.events.find_one({})
    
    if event:
        event_id = str(event['_id'])
        print(f"   Using event ID: {event_id}")
        
        response = client.get(f"/api/advice/event/{event_id}?limit=20&offset=0")
        print(f"   Status code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   Error: {response.text}")
        else:
            print(f"   Success! Retrieved {len(response.json())} advice items")
    else:
        print("   No events found in database")
    
    # Test 2: Test POST /api/advice/ without auth
    print("\n2. Testing POST /api/advice/ (without auth)")
    advice_data = {
        "event_id": event_id if 'event_id' in locals() else "685bda664009b338adca0809",
        "title": "Test Advice",
        "content": "This is a test advice",
        "category": "general",
        "advice_type": "attended_similar",
        "tags": [],
        "venue_familiarity": False,
        "language": "en"
    }
    
    response = client.post("/api/advice/", json=advice_data)
    print(f"   Status code: {response.status_code}")
    print(f"   Response: {response.text[:200]}...")
    
    # Test 3: Check if endpoints are properly registered
    print("\n3. Checking registered routes:")
    for route in app.routes:
        if "/advice" in str(route.path):
            print(f"   {route.methods} {route.path}")
    
    mongo_client.close()

if __name__ == "__main__":
    test_advice_endpoints()