#!/usr/bin/env python3
"""
Test AI image generation on existing events
"""

import os
import asyncio
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from ai_image_service_hybrid import HybridAIImageService
from loguru import logger

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'DataCollection.env'))

async def test_ai_generation_on_existing():
    """Test AI image generation on existing events without images"""
    
    print("🎨 Testing AI Image Generation on Existing Events")
    print("=" * 60)
    
    # Connect to MongoDB
    mongodb_uri = os.getenv('MONGO_URI')  # Match your env variable name
    if not mongodb_uri:
        print("❌ MONGO_URI not found in environment")
        return
    
    print(f"🔗 Connecting to MongoDB...")
    client = AsyncIOMotorClient(mongodb_uri, tlsInsecure=True)
    db = client['DXB']
    
    try:
        # Find events without AI images
        events_without_images = await db.events.find({
            "$or": [
                {"images.ai_generated": {"$exists": False}},
                {"images.ai_generated": None},
                {"images.status": {"$ne": "completed_hybrid"}}
            ]
        }).limit(5).to_list(length=5)  # Test with 5 events
        
        if not events_without_images:
            print("✅ All events already have AI images!")
            return
        
        print(f"🎯 Found {len(events_without_images)} events without AI images")
        print("📋 Events to process:")
        for i, event in enumerate(events_without_images, 1):
            title = event.get('title', 'Unknown Event')
            description = event.get('description', '')[:80]
            print(f"   {i}. {title}")
            print(f"      {description}{'...' if len(event.get('description', '')) > 80 else ''}")
        print()
        
        # Initialize AI service
        ai_service = HybridAIImageService()
        
        success_count = 0
        failed_count = 0
        
        for i, event in enumerate(events_without_images, 1):
            event_title = event.get('title', 'Unknown Event')
            print(f"🎨 [{i}/{len(events_without_images)}] Generating image for: {event_title}")
            
            try:
                # Generate prompt to show what will be used
                prompt = ai_service._create_hybrid_prompt(event)
                print(f"   📝 Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
                
                # Generate AI image
                image_url = await ai_service.generate_image(event)
                
                if image_url:
                    # Update event with image
                    await ai_service.update_event_with_image(
                        db, event['_id'], image_url, prompt
                    )
                    
                    success_count += 1
                    print(f"   ✅ Generated: {image_url[:60]}...")
                else:
                    failed_count += 1
                    print(f"   ❌ Failed to generate image")
                
                # Small delay between generations
                if i < len(events_without_images):
                    print(f"   ⏸️ Waiting 5 seconds...")
                    await asyncio.sleep(5)
                
            except Exception as e:
                failed_count += 1
                print(f"   ❌ Error: {str(e)}")
        
        print("\n🎉 AI Image Generation Test Complete!")
        print(f"   ✅ Successful: {success_count}")
        print(f"   ❌ Failed: {failed_count}")
        print(f"   📊 Success rate: {(success_count / (success_count + failed_count) * 100):.1f}%")
        
        if success_count > 0:
            print(f"\n🌐 Opening gallery of generated images...")
            await show_generated_images(db, success_count)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()

async def show_generated_images(db, limit=5):
    """Show recently generated images"""
    
    recent_images = await db.events.find({
        "images.ai_generated": {"$exists": True, "$ne": None}
    }).sort("images.generated_at", -1).limit(limit).to_list(length=limit)
    
    if recent_images:
        import webbrowser
        import tempfile
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>AI Generated Images Test Results</title>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white; 
                    padding: 20px; 
                    margin: 0;
                }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                h1 {{ text-align: center; color: #fff; }}
                .grid {{ 
                    display: grid; 
                    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); 
                    gap: 20px; 
                    margin-top: 30px; 
                }}
                .card {{ 
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 15px; 
                    padding: 20px; 
                    border: 1px solid rgba(255, 255, 255, 0.2);
                }}
                .card img {{ 
                    width: 100%; 
                    height: 250px; 
                    object-fit: cover; 
                    border-radius: 10px; 
                    margin-bottom: 15px; 
                }}
                .title {{ font-size: 1.2em; font-weight: bold; margin-bottom: 10px; }}
                .prompt {{ 
                    background: rgba(0, 0, 0, 0.3);
                    padding: 10px; 
                    border-radius: 8px; 
                    font-size: 0.8em; 
                    margin-top: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎨 AI Generated Images - Test Results</h1>
                <div class="grid">
        """
        
        for event in recent_images:
            title = event.get('title', 'Unknown Event')
            image_url = event.get('images', {}).get('ai_generated', '')
            prompt = event.get('images', {}).get('prompt_used', 'No prompt stored')
            
            html += f"""
                <div class="card">
                    <img src="{image_url}" alt="{title}" />
                    <div class="title">{title}</div>
                    <div class="prompt">
                        <strong>Prompt Used:</strong><br>
                        {prompt[:200]}{'...' if len(prompt) > 200 else ''}
                    </div>
                </div>
            """
        
        html += """
                </div>
            </div>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html)
            temp_file = f.name
        
        webbrowser.open(f'file://{temp_file}')
        print(f"✅ Gallery opened: {temp_file}")

if __name__ == "__main__":
    asyncio.run(test_ai_generation_on_existing())