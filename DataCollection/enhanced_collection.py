#!/usr/bin/env python3
"""
Enhanced hybrid event collection with Perplexity AI and Firecrawl MCP
Collects events from multiple sources with integrated deduplication
"""

import asyncio
import json
import os
from datetime import datetime
from perplexity_events_extractor import DubaiEventsPerplexityExtractor
from firecrawl_mcp_extractor import FirecrawlMCPExtractor
from perplexity_storage import PerplexityEventsStorage
from ai_image_service_hybrid import HybridAIImageService
from loguru import logger

async def generate_ai_images_for_stored_events(storage, stored_count):
    """Generate AI images for recently stored events"""
    
    try:
        logger.info(f'🎨 Starting AI image generation for {stored_count} stored events...')
        
        # Initialize AI image service
        ai_service = HybridAIImageService()
        
        # Get database connection from storage
        db = storage.db
        
        # Find events without AI images (recently stored events)
        events_needing_images = await db.events.find({
            "$or": [
                {"images.ai_generated": {"$exists": False}},
                {"images.ai_generated": None},
                {"images.status": {"$ne": "completed_hybrid"}}
            ]
        }).to_list(length=None)
        
        if not events_needing_images:
            logger.info('✅ All events already have AI images')
            return
        
        logger.info(f'🎯 Found {len(events_needing_images)} events needing AI images')
        
        # Process events in batches to manage API rate limits
        batch_size = int(os.getenv('AI_IMAGE_BATCH_SIZE', '5'))
        success_count = 0
        failed_count = 0
        
        for i in range(0, len(events_needing_images), batch_size):
            batch = events_needing_images[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(events_needing_images) + batch_size - 1) // batch_size
            
            logger.info(f'📦 Processing batch {batch_num}/{total_batches}: {len(batch)} events')
            
            # Process batch sequentially to respect API limits
            for event in batch:
                try:
                    event_title = event.get('title', 'Unknown Event')
                    logger.info(f'🎨 Generating image for: {event_title}')
                    
                    # Generate AI image with hybrid approach
                    image_url = await ai_service.generate_image(event)
                    
                    if image_url:
                        # Create prompt for storage
                        prompt_used = ai_service._create_hybrid_prompt(event)
                        
                        # Update event with generated image
                        await ai_service.update_event_with_image(
                            db, event['_id'], image_url, prompt_used
                        )
                        
                        success_count += 1
                        logger.info(f'✅ Generated image for: {event_title}')
                    else:
                        failed_count += 1
                        logger.warning(f'❌ Failed to generate image for: {event_title}')
                        
                        # Mark as failed in database
                        await db.events.update_one(
                            {"_id": event['_id']},
                            {
                                "$set": {
                                    "images.status": "failed",
                                    "images.failed_at": datetime.now().isoformat(),
                                    "images.error": "AI generation failed"
                                }
                            }
                        )
                
                except Exception as e:
                    failed_count += 1
                    event_title = event.get('title', 'Unknown Event')
                    logger.error(f'❌ Error generating image for {event_title}: {str(e)}')
            
            # Rate limiting between batches (except for last batch)
            if i + batch_size < len(events_needing_images):
                delay = int(os.getenv('AI_IMAGE_BATCH_DELAY', '10'))
                logger.info(f'⏸️ Waiting {delay} seconds between batches...')
                await asyncio.sleep(delay)
        
        # Final summary
        logger.info(f'🎉 AI Image Generation Complete!')
        logger.info(f'   ✅ Successfully generated: {success_count} images')
        logger.info(f'   ❌ Failed: {failed_count} images')
        logger.info(f'   📊 Success rate: {(success_count / (success_count + failed_count) * 100):.1f}%')
        
    except Exception as e:
        logger.error(f'❌ Error in AI image generation: {str(e)}')
        import traceback
        logger.error(f'Full traceback: {traceback.format_exc()}')

async def collect_and_store_events():
    try:
        storage = PerplexityEventsStorage()
        
        # Check if Firecrawl supplement is enabled
        enable_firecrawl = os.getenv('ENABLE_FIRECRAWL_SUPPLEMENT', 'false').lower() == 'true'
        
        # Check if AI image generation is enabled  
        enable_ai_images = os.getenv('ENABLE_AI_IMAGE_GENERATION', 'true').lower() == 'true'
        
        logger.info('🚀 Starting hybrid event discovery...')
        logger.info(f'🔧 Firecrawl supplement: {"ENABLED" if enable_firecrawl else "DISABLED"}')
        logger.info(f'🎨 AI image generation: {"ENABLED" if enable_ai_images else "DISABLED"}')
        
        all_events = []
        perplexity_events = []
        firecrawl_events = []
        
        # Phase 1: Perplexity AI extraction
        logger.info('📡 Phase 1: Perplexity AI event discovery')
        try:
            perplexity_extractor = DubaiEventsPerplexityExtractor()
            perplexity_events = await perplexity_extractor.discover_events_by_categories()
            logger.info(f'📊 Perplexity Phase 1 completed: {len(perplexity_events)} events')
            
            # Ensure Perplexity extractor is properly cleaned up
            del perplexity_extractor
            
        except Exception as e:
            logger.error(f'❌ Perplexity extraction failed: {e}')
            perplexity_events = []
        
        # Add Perplexity events to collection
        all_events.extend(perplexity_events)
        
        # Phase 2: Optional Firecrawl MCP extraction
        if enable_firecrawl:
            logger.info('🔥 Phase 2: Firecrawl MCP supplemental extraction')
            try:
                firecrawl_extractor = FirecrawlMCPExtractor()
                
                # Get daily limits from environment
                firecrawl_limits = {
                    'platinumlist': int(os.getenv('FIRECRAWL_PLATINUMLIST_LIMIT', '25')),
                    'timeout': int(os.getenv('FIRECRAWL_TIMEOUT_LIMIT', '15')),
                    'whatson': int(os.getenv('FIRECRAWL_WHATSON_LIMIT', '10'))
                }
                
                firecrawl_results = await firecrawl_extractor.extract_all_sources(firecrawl_limits)
                
                # Flatten Firecrawl results
                for source, events in firecrawl_results.items():
                    firecrawl_events.extend(events)
                    logger.info(f'🔥 {source}: {len(events)} events')
                
                logger.info(f'📊 Firecrawl Phase 2 completed: {len(firecrawl_events)} events')
                
                # Ensure Firecrawl extractor is properly cleaned up
                del firecrawl_extractor
                
                # Add Firecrawl events to the collection
                all_events.extend(firecrawl_events)
                
            except Exception as e:
                logger.error(f'❌ Firecrawl extraction failed: {e}')
                logger.error(f'❌ Firecrawl error details: {str(e)}')
                firecrawl_events = []
        
        # Log final hybrid extraction summary
        logger.info(f'🎯 FINAL Hybrid extraction summary:')
        logger.info(f'   📡 Perplexity: {len(perplexity_events)} events')
        logger.info(f'   🔥 Firecrawl: {len(firecrawl_events)} events')
        logger.info(f'   📊 Total before dedup: {len(all_events)} events')
        logger.info(f'🛑 EVENT EXTRACTION PHASES COMPLETED - Starting storage phase')
        
        logger.info(f'📊 Total events before storage: {len(all_events)}')
        
        if all_events:
            # Debug: Print first event structure
            logger.info(f'📋 First event keys: {list(all_events[0].keys()) if all_events else "None"}')
            
            # Create extraction session
            session_type = 'hybrid_collection' if enable_firecrawl else 'perplexity_collection'
            session_id = storage.create_extraction_session(session_type)
            logger.info(f'📝 Created session: {session_id}')
            
            # Store events one by one to identify exact issue
            stored_count = 0
            for i, event in enumerate(all_events):
                try:
                    # Verify event is a dictionary
                    if not isinstance(event, dict):
                        logger.error(f"❌ Event {i} is not a dict: {type(event)}")
                        continue
                    
                    # Store single event with deduplication
                    result = await storage.store_events([event], session_id)
                    
                    if result.get('stored_count', 0) > 0:
                        stored_count += 1
                        if stored_count % 10 == 0:
                            logger.info(f"✅ Stored {stored_count} events so far...")
                    
                except Exception as e:
                    logger.error(f"❌ Error storing event {i}: {e}")
                    logger.error(f"Event data: {json.dumps(event, indent=2, default=str)}")
                    continue
            
            logger.info(f"✅ Successfully stored {stored_count} out of {len(all_events)} events")
            
            # Update session with hybrid extraction details
            session_update = {
                'total_events': len(all_events),
                'stored_events': stored_count,
                'status': 'completed',
                'extraction_method': 'hybrid' if enable_firecrawl else 'perplexity_only'
            }
            
            if enable_firecrawl:
                session_update.update({
                    'perplexity_events': len(perplexity_events),
                    'firecrawl_events': len(firecrawl_events),
                    'firecrawl_enabled': True
                })
            
            storage.update_extraction_session(session_id, session_update)
            
            logger.info(f'🏁 HYBRID COLLECTION COMPLETED SUCCESSFULLY')
            
            # Phase 3: AI Image Generation (if enabled)
            if enable_ai_images and stored_count > 0:
                logger.info('🎨 Phase 3: AI Image Generation')
                await generate_ai_images_for_stored_events(storage, stored_count)
            
            logger.info(f'📊 Final Summary:')
            logger.info(f'   📡 Perplexity events stored: {len(perplexity_events)}')
            logger.info(f'   🔥 Firecrawl events stored: {len(firecrawl_events)}')
            logger.info(f'   💾 Total unique events stored: {stored_count}')
        
        storage.close()
        return stored_count if all_events else 0
        
    except Exception as e:
        logger.error(f'❌ Error: {e}')
        import traceback
        logger.error(f'Full traceback: {traceback.format_exc()}')
        return 0

if __name__ == "__main__":
    result = asyncio.run(collect_and_store_events())
    logger.success(f'✅ Collection completed! Total events discovered: {result}')