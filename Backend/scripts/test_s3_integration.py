#!/usr/bin/env python3
"""
Test S3 Integration
Tests AI image generation and storage in S3
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add Backend path for imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from utils.ai_image_service_s3 import create_ai_image_service_s3

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', 'Backend.env'))

async def test_ai_image_generation():
    """Test AI image generation with S3 storage"""
    print("🧪 Testing AI Image Generation with S3 Storage")
    print("=" * 50)
    
    try:
        # Create AI image service
        ai_service = create_ai_image_service_s3()
        print("✅ AI Image Service initialized")
        
        # Test event data
        test_event = {
            '_id': 'test_event_001',
            'name': 'Test Dubai Event',
            'description': 'A test event for AI image generation in Dubai',
            'category': 'entertainment',
            'venue': {
                'name': 'Test Venue',
                'area': 'Dubai Marina'
            }
        }
        
        print(f"🎯 Test Event: {test_event['name']}")
        print(f"📍 Venue: {test_event['venue']['name']} in {test_event['venue']['area']}")
        
        # Generate AI image
        print("\n🎨 Generating AI image...")
        s3_url = await ai_service.generate_event_image(test_event)
        
        if s3_url:
            print(f"✅ AI image generated successfully!")
            print(f"🔗 S3 URL: {s3_url}")
            
            # Verify the image is accessible
            print("\n🔍 Verifying image accessibility...")
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.head(s3_url) as response:
                    if response.status == 200:
                        print("✅ Image is accessible via S3 URL")
                        print(f"📏 Content-Length: {response.headers.get('Content-Length', 'Unknown')}")
                        print(f"📄 Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
                    else:
                        print(f"❌ Image not accessible: HTTP {response.status}")
        else:
            print("❌ AI image generation failed")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

async def test_batch_processing():
    """Test batch processing of multiple events"""
    print("\n🔄 Testing Batch Processing")
    print("=" * 30)
    
    try:
        # Create AI image service
        ai_service = create_ai_image_service_s3()
        
        # Test events
        test_events = [
            {
                '_id': 'batch_test_001',
                'name': 'Dubai Food Festival',
                'description': 'Culinary celebration in Dubai',
                'category': 'dining'
            },
            {
                '_id': 'batch_test_002',
                'name': 'Marina Beach Party',
                'description': 'Beach party at Dubai Marina',
                'category': 'nightlife'
            }
        ]
        
        print(f"📦 Processing {len(test_events)} events...")
        
        # Process batch
        results = await ai_service.process_events_batch(test_events)
        
        # Display results
        print("\n📊 Batch Results:")
        for event_id, s3_url in results.items():
            if s3_url:
                print(f"  ✅ {event_id}: {s3_url[:60]}...")
            else:
                print(f"  ❌ {event_id}: Failed")
                
    except Exception as e:
        print(f"❌ Batch test failed: {e}")

async def test_duplicate_prevention():
    """Test duplicate prevention mechanism"""
    print("\n🚫 Testing Duplicate Prevention")
    print("=" * 30)
    
    try:
        # Create AI image service
        ai_service = create_ai_image_service_s3()
        
        # Test event with existing image
        test_event = {
            '_id': 'duplicate_test_001',
            'name': 'Existing Image Event',
            'description': 'Event that already has an AI image',
            'category': 'entertainment',
            'images': {
                'ai_generated': 'https://mydscvr-event-images.s3.me-central-1.amazonaws.com/events/existing_image.jpg'
            }
        }
        
        print("🔍 Testing with event that has existing AI image...")
        
        # Try to generate (should skip)
        result = await ai_service.generate_event_image(test_event)
        
        if result == test_event['images']['ai_generated']:
            print("✅ Duplicate prevention working - returned existing image")
        else:
            print("❌ Duplicate prevention failed - new image generated")
            
    except Exception as e:
        print(f"❌ Duplicate prevention test failed: {e}")

async def main():
    """Run all tests"""
    print("🚀 S3 Integration Test Suite")
    print("=" * 50)
    
    # Check configuration
    required_env_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'OPENAI_API_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Please run: python Backend/scripts/setup_s3_config.py")
        return
    
    s3_bucket = os.getenv('S3_BUCKET_NAME', 'mydscvr-event-images')
    aws_region = os.getenv('AWS_REGION', 'me-central-1')
    
    print(f"📦 S3 Bucket: {s3_bucket}")
    print(f"🌍 AWS Region: {aws_region}")
    print(f"🔑 OpenAI API Key: {'*' * 20}...{os.getenv('OPENAI_API_KEY', '')[-4:]}")
    
    # Run tests
    try:
        await test_ai_image_generation()
        await test_batch_processing()
        await test_duplicate_prevention()
        
        print("\n✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())