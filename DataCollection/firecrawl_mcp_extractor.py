#!/usr/bin/env python3
"""
Firecrawl MCP Event Extractor for Dubai Events
Real integration with Firecrawl MCP to extract events from Dubai event sources
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import os
from loguru import logger
from dotenv import load_dotenv
import subprocess
import tempfile

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'AI_API.env'))

class FirecrawlMCPExtractor:
    """
    Firecrawl MCP-based extractor for Dubai events from multiple sources
    Uses the same event schema as the Perplexity extractor for consistency
    """
    
    def __init__(self):
        self.api_key = os.getenv('FIRECRAWL_API_KEY')
        if not self.api_key:
            raise ValueError("FIRECRAWL_API_KEY environment variable is required but not set")
        
        # Source configurations
        self.sources = {
            'platinumlist': {
                'base_url': 'https://dubai.platinumlist.net/',
                'search_patterns': [
                    'https://dubai.platinumlist.net/events',
                    'https://dubai.platinumlist.net/attractions',
                    'https://dubai.platinumlist.net/concerts',
                ],
                'priority': 'high',
                'daily_limit': 25,
                'strengths': ['pricing', 'booking_links', 'venue_details', 'structured_data']
            },
            'timeout': {
                'base_url': 'https://www.timeoutdubai.com/',
                'search_patterns': [
                    'https://www.timeoutdubai.com/things-to-do/events',
                    'https://www.timeoutdubai.com/nightlife',
                    'https://www.timeoutdubai.com/kids',
                ],
                'priority': 'high', 
                'daily_limit': 15,
                'strengths': ['editorial_content', 'recommendations', 'descriptions', 'reviews']
            },
            'whatson': {
                'base_url': 'https://whatson.ae/',
                'search_patterns': [
                    'https://whatson.ae/dubai/events',
                    'https://whatson.ae/dubai/activities',
                    'https://whatson.ae/dubai/kids',
                ],
                'priority': 'medium',
                'daily_limit': 10,
                'strengths': ['family_events', 'comprehensive_listings', 'local_activities']
            }
        }
        
        # Configure logging
        logger.add("logs/firecrawl_mcp_extraction.log", rotation="10 MB", retention="7 days")
        
        # Use sophisticated extraction prompt from perplexity_events_extractor.py
        # Initialization complete - sophisticated prompts defined in methods below

    async def _call_firecrawl_mcp_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Call Firecrawl MCP tools using the proper MCP protocol
        """
        try:
            # Import MCP client libraries
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            
            # Set up MCP client for Firecrawl
            server_params = StdioServerParameters(
                command="npx",
                args=["-y", "firecrawl-mcp"],
                env={
                    "FIRECRAWL_API_KEY": self.api_key
                }
            )
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize the session
                    await session.initialize()
                    
                    # List available tools to verify
                    tools = await session.list_tools()
                    logger.debug(f"Available MCP tools: {[tool.name for tool in tools.tools]}")
                    
                    # Call the specified tool
                    result = await session.call_tool(tool_name, kwargs)
                    
                    return {
                        "success": True,
                        "content": result.content,
                        "isError": result.isError
                    }
                    
        except ImportError:
            logger.error("MCP libraries not available. Install with: pip install mcp")
            return {"error": "MCP libraries not installed"}
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {str(e)}")
            return {"error": str(e)}

    async def map_source_urls(self, source_name: str, limit: int = 20) -> List[str]:
        """
        Map URLs from a source using Firecrawl MCP tools
        """
        if source_name not in self.sources:
            logger.error(f"Unknown source: {source_name}")
            return []
        
        source_config = self.sources[source_name]
        all_urls = []
        
        for pattern_url in source_config['search_patterns']:
            logger.info(f"🗺️ Mapping URLs from {pattern_url}")
            
            # Call Firecrawl MCP map tool
            result = await self._call_firecrawl_mcp_tool(
                'firecrawl_map',
                url=pattern_url,
                search='events activities Dubai',
                limit=max(1, limit // len(source_config['search_patterns']))  # Ensure minimum 1
            )
            
            if result.get('success') and not result.get('isError'):
                # Parse the MCP response content
                content = result.get('content', [])
                if content and len(content) > 0:
                    # Extract URLs from MCP response - handle TextContent objects
                    text_content = ""
                    if hasattr(content[0], 'text'):
                        text_content = content[0].text
                    elif isinstance(content[0], dict) and 'text' in content[0]:
                        text_content = content[0]['text']
                    
                    try:
                        # Try to parse as JSON if it's structured
                        import json
                        data = json.loads(text_content)
                        urls = data.get('links', []) if isinstance(data, dict) else []
                    except json.JSONDecodeError:
                        # Fallback: extract URLs from text using regex
                        import re
                        urls = re.findall(r'https?://[^\s]+', text_content)
                    
                    all_urls.extend(urls)
                    logger.info(f"📍 Found {len(urls)} URLs from {pattern_url}")
                else:
                    logger.warning(f"⚠️ No content in MCP response for {pattern_url}")
            else:
                error_msg = result.get('error', 'Unknown MCP error')
                logger.warning(f"⚠️ Failed to map {pattern_url}: {error_msg}")
        
        # Remove duplicates and limit results
        unique_urls = list(dict.fromkeys(all_urls))[:limit]
        logger.info(f"✅ Total unique URLs mapped from {source_name}: {len(unique_urls)}")
        
        return unique_urls

    async def scrape_and_parse_url(self, url: str, source_name: str) -> List[Dict[str, Any]]:
        """
        Scrape URL with Firecrawl and parse with Perplexity
        """
        logger.info(f"🔍 Scraping and parsing: {url}")
        
        # Step 1: Scrape with Firecrawl MCP
        result = await self._call_firecrawl_mcp_tool(
            'firecrawl_scrape',
            url=url,
            formats=['markdown']
        )
        
        if not result.get('success') or result.get('isError'):
            error_msg = result.get('error', 'Unknown MCP error')
            logger.warning(f"⚠️ Failed to scrape {url}: {error_msg}")
            return []
        
        # Step 2: Extract content from MCP response
        content = result.get('content', [])
        if not content:
            logger.warning(f"⚠️ No content returned from {url}")
            return []
        
        # Handle TextContent objects properly
        text_content = ""
        if hasattr(content[0], 'text'):
            text_content = content[0].text
        elif isinstance(content[0], dict) and 'text' in content[0]:
            text_content = content[0]['text']
        
        if not text_content:
            logger.warning(f"⚠️ Empty content from {url}")
            return []
        
        # Step 3: Parse with Perplexity using sophisticated prompts
        try:
            from perplexity_events_extractor import DubaiEventsPerplexityExtractor
            perplexity_extractor = DubaiEventsPerplexityExtractor()
            
            # Create sophisticated extraction prompt tailored for scraped content
            extraction_prompt = self._create_sophisticated_extraction_prompt_for_scraped_content(text_content, source_name, url)
            
            # Use the sophisticated prompt for parsing
            parse_result = await self._parse_with_sophisticated_prompt(perplexity_extractor, extraction_prompt)
            
            events = parse_result.get('events', []) if parse_result else []
            
            # Add enhanced source metadata to each event
            for event in events:
                if isinstance(event, dict):
                    event.update({
                        'extraction_source': f'firecrawl_{source_name}',
                        'extraction_method': 'firecrawl_scrape_perplexity_sophisticated_parse',
                        'extraction_timestamp': datetime.now().isoformat(),
                        'source_url': url,
                        'source_reliability': self.sources[source_name]['priority'],
                        'content_length': len(text_content),
                        'firecrawl_quality': 'high' if len(text_content) > 1000 else 'medium'
                    })
            
            logger.info(f"📊 Scraped and parsed {len(events)} events from {url} using sophisticated prompts")
            return events
            
        except Exception as e:
            logger.error(f"❌ Error parsing content from {url}: {str(e)}")
            return []

    async def extract_from_source(self, source_name: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        Extract events from a specific source using Firecrawl MCP
        """
        logger.info(f"🚀 Starting Firecrawl MCP extraction from {source_name}")
        
        if source_name not in self.sources:
            raise ValueError(f"Unknown source: {source_name}")
        
        source_config = self.sources[source_name]
        limit = limit or source_config['daily_limit']
        
        extracted_events = []
        
        try:
            # Step 1: Map URLs from the source
            urls = await self.map_source_urls(source_name, limit)
            
            if not urls:
                logger.warning(f"⚠️ No URLs found for {source_name}")
                return []
            
            # Step 2: Scrape and parse events from discovered URLs
            logger.info(f"🎯 Scraping and parsing events from {len(urls)} URLs")
            
            # Process URLs in batches to avoid overwhelming the API
            batch_size = 2  # Reduced since we're now doing Perplexity calls too
            for i in range(0, len(urls), batch_size):
                batch_urls = urls[i:i+batch_size]
                
                # Process batch sequentially to avoid API limits
                for url in batch_urls:
                    try:
                        events = await self.scrape_and_parse_url(url, source_name)
                        extracted_events.extend(events)
                    except Exception as e:
                        logger.error(f"❌ Error scraping/parsing {url}: {str(e)}")
                
                # Rate limiting between batches
                if i + batch_size < len(urls):
                    await asyncio.sleep(3)  # Longer delay due to Perplexity calls
            
        except Exception as e:
            logger.error(f"❌ Error extracting from {source_name}: {str(e)}")
        
        logger.info(f"✅ Extracted {len(extracted_events)} events from {source_name}")
        return extracted_events

    async def extract_all_sources(self, limits: Dict[str, int] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract events from all configured sources
        """
        logger.info("🚀 Starting comprehensive Firecrawl MCP extraction from all sources")
        
        limits = limits or {}
        results = {}
        
        # Extract from each source sequentially to be respectful to APIs
        for source_name in self.sources.keys():
            limit = limits.get(source_name, None)
            
            try:
                events = await self.extract_from_source(source_name, limit)
                results[source_name] = events
                logger.info(f"✅ {source_name}: {len(events)} events extracted")
                
                # Small delay between sources
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Failed to extract from {source_name}: {str(e)}")
                results[source_name] = []
        
        total_events = sum(len(events) for events in results.values())
        logger.info(f"🎯 Total events extracted: {total_events}")
        
        return results

    def _create_sophisticated_extraction_prompt_for_scraped_content(self, content: str, source_name: str, url: str) -> Dict[str, str]:
        """
        Create sophisticated extraction prompt based on the perplexity_events_extractor.py approach
        Tailored for scraped content rather than web search
        """
        
        system_prompt = """You are a Dubai Events specialist. Extract current Dubai events from the provided scraped content. Return ONLY valid JSON with event data and family scores. Be precise and focus on real events happening soon."""
        
        main_prompt = f"""
TASK: Extract ALL Dubai events from this {source_name} website content: {url}

CONTEXT: This content was scraped from {source_name}, a trusted Dubai events source. Extract every event you can find, regardless of target audience. 
We'll use family scoring and filtering on the frontend, but the database should contain ALL Dubai events.

SOURCE CONTENT:
{content[:4000]}...

EXTRACTION REQUIREMENTS:
Extract event information from the scraped content above.

Return a JSON object with an "events" array containing ALL event information found.

For each event, extract:

1. BASIC INFORMATION:
   - title: Clear, descriptive event name
   - description: Full description from source (200-500 characters)
   - ai_summary: Create a 100-150 character engaging summary highlighting what makes it special

2. DATE & TIME:
   - start_date: ISO format (YYYY-MM-DDTHH:MM:SS) - if no specific time, use reasonable defaults
   - end_date: ISO format (if available, null if not specified)
   - duration_hours: Estimated duration (1-8 hours based on event type)
   - recurring: true/false if it's a recurring event

3. VENUE DETAILS:
   - venue_name: Official venue name
   - address: Full address if available
   - area: Dubai area (Dubai Marina, JBR, Downtown, DIFC, Jumeirah, Business Bay, etc.)
   - venue_type: "indoor"/"outdoor"/"both"
   - parking_available: true/false/unknown (infer from venue type)
   - metro_accessible: true/false/unknown (infer from area knowledge)

4. PRICING (in AED):
   - min_price: Lowest price (0 for free events)
   - max_price: Highest price (same as min if single price)
   - currency: "AED"
   - free_for_children: true/false (if children under certain age are free)
   - pricing_notes: Any special pricing details

5. AUDIENCE & SUITABILITY:
   - target_audience: ["adults", "families", "children", "teens", "seniors", "professionals", "tourists", "couples"]
   - age_restrictions: "18+", "21+", "all_ages", "children_only", etc.
   - dress_code: "casual", "smart_casual", "formal", "themed", "none"

6. FAMILY ANALYSIS (for filtering purposes):
   - family_friendly: true/false (can families with children attend?)
   - child_age_min: Minimum recommended child age (0-18, null if not suitable for children)
   - child_age_max: Maximum recommended child age (0-18, null if no upper limit)
   - stroller_accessible: true/false/unknown (based on venue and activity type)
   - requires_supervision: true/false (if children need adult supervision)
   - educational_value: "none", "low", "medium", "high"
   - child_activity_level: "passive", "low", "medium", "high"

7. EVENT CATEGORIZATION:
   - primary_category: Main category from: [
     "nightlife", "dining", "business", "networking", "cultural", "arts", "music", 
     "sports", "fitness", "entertainment", "shopping", "educational", "workshops",
     "outdoor", "adventure", "beach", "water_sports", "family", "children", 
     "festivals", "seasonal", "religious", "community", "charity", "technology",
     "health_wellness", "beauty", "fashion", "automotive", "real_estate"
   ]
   - secondary_categories: Array of additional relevant categories from the same list
   - event_type: "conference", "workshop", "concert", "party", "exhibition", "festival", 
                 "sports_event", "dining_experience", "tour", "class", "meetup", "show", etc.
   - indoor_outdoor: "indoor", "outdoor", "both"
   - special_occasion: "weekend", "holiday", "ramadan", "eid", "national_day", "valentine", "mothers_day", etc. (null if regular event)

8. ACCESSIBILITY & LOGISTICS:
   - special_needs_friendly: true/false/unknown
   - language_requirements: "arabic", "english", "bilingual", "multilingual", "none"
   - transportation_notes: Any specific transport information
   - alcohol_served: true/false/unknown (important for cultural considerations)

9. FAMILY SCORE CALCULATION (0-100, for frontend filtering):
   Calculate ONLY if family_friendly is true, otherwise set to 0:
   - Age inclusivity: Wider child age range = higher score
   - Safety & supervision: Supervised, stroller-accessible = higher score
   - Educational value: Learning opportunities = higher score
   - Duration: 1-4 hours ideal for families = higher score
   - Venue accessibility: Metro accessible, parking = higher score
   - Pricing: Free or reasonable pricing = higher score
   - Time: Weekend or evening timing = higher score
   
   For non-family events (nightlife, 18+ events, etc.), always set family_score to 0.

10. METADATA:
   - source: "{source_name}"
   - source_url: "{url}"
   - event_url: Direct URL to the event page (specific event, not just domain)
   - scraped_at: Current timestamp
   - image_urls: Array of image URLs if found
   - booking_required: true/false
   - contact_info: Phone/email if available
   - ticket_links: Array of booking/ticket URLs
   - social_media: {{
       "instagram": "@handle or full URL",
       "facebook": "facebook.com/event or @handle",
       "twitter": "@handle",
       "tiktok": "@handle",
       "youtube": "channel URL",
       "whatsapp": "group link if available",
       "telegram": "channel if available"
     }}
   - quality_metrics: {{
       "extraction_confidence": 0.0-1.0,
       "data_completeness": 0.0-1.0,
       "source_reliability": "high"/"medium"/"low",
       "last_verified": timestamp,
       "extraction_method": "firecrawl_scrape_perplexity_parse",
       "validation_warnings": []
     }}

EXTRACTION STANDARDS:
- Extract ALL events found in the content, regardless of audience
- Include nightlife, business events, dining experiences, cultural events, sports, entertainment - everything
- Don't filter out adult-only events - mark them appropriately with family_friendly: false
- Include events without clear dates but mark them appropriately with reasonable date estimates
- Extract partial information rather than skipping events
- For unclear information, use "unknown" rather than guessing
- Focus on events happening in the next 3 months (June-August 2025) but include ongoing events and future seasonal events

RESPONSE FORMAT:
Return ONLY valid JSON in this exact structure:
{{
  "events": [
    {{
      "title": "Event Title",
      "description": "Full event description...",
      "ai_summary": "Engaging 100-150 character summary...",
      "start_date": "2025-01-15T19:00:00",
      "end_date": "2025-01-15T23:00:00",
      "duration_hours": 4,
      "recurring": false,
      "venue_name": "Venue Name",
      "address": "Full address, Dubai",
      "area": "Downtown",
      "venue_type": "indoor",
      "parking_available": true,
      "metro_accessible": true,
      "min_price": 150,
      "max_price": 300,
      "currency": "AED",
      "free_for_children": false,
      "pricing_notes": "Special pricing details",
      "target_audience": ["adults", "couples"],
      "age_restrictions": "21+",
      "dress_code": "smart_casual",
      "family_friendly": false,
      "child_age_min": null,
      "child_age_max": null,
      "stroller_accessible": false,
      "requires_supervision": false,
      "educational_value": "none",
      "child_activity_level": "passive",
      "primary_category": "nightlife",
      "secondary_categories": ["music", "dining"],
      "event_type": "concert",
      "indoor_outdoor": "indoor",
      "special_occasion": null,
      "special_needs_friendly": "unknown",
      "language_requirements": "english",
      "transportation_notes": "Valet parking available",
      "alcohol_served": true,
      "family_score": 0,
      "source": "{source_name}",
      "source_url": "{url}",
      "event_url": "https://example.com/event/dubai-concert-2025",
      "scraped_at": "{datetime.now().isoformat()}",
      "image_urls": ["https://example.com/image.jpg"],
      "booking_required": true,
      "contact_info": "contact@venue.com",
      "ticket_links": ["https://tickets.com/event"],
      "social_media": {{
        "instagram": "@venue",
        "facebook": "facebook.com/venueevents",
        "twitter": "@venue_dubai",
        "tiktok": "@venuedubai",
        "youtube": null,
        "whatsapp": null,
        "telegram": null
      }},
      "quality_metrics": {{
        "extraction_confidence": 0.85,
        "data_completeness": 0.80,
        "source_reliability": "high",
        "last_verified": "{datetime.now().isoformat()}",
        "extraction_method": "firecrawl_scrape_perplexity_parse",
        "validation_warnings": []
      }}
    }}
  ],
  "extraction_metadata": {{
    "total_events_found": 1,
    "family_events_count": 0,
    "adult_events_count": 1,
    "source_name": "{source_name}",
    "source_url": "{url}",
    "processing_timestamp": "{datetime.now().isoformat()}",
    "extraction_quality": "high"
  }}
}}

IMPORTANT: 
- Extract ALL events from the provided content
- Use family_friendly and family_score for filtering capabilities
- Return ONLY the JSON response, no additional text
- Ensure all dates are in correct ISO format
- Family scores should only be calculated for family_friendly events
- Include metadata about the extraction process
"""
        
        return {
            "system_prompt": system_prompt,
            "main_prompt": main_prompt
        }
    
    async def _parse_with_sophisticated_prompt(self, perplexity_extractor, extraction_prompt: Dict[str, str]) -> Dict[str, Any]:
        """
        Use the Perplexity extractor's API with our sophisticated prompt for scraped content
        """
        import httpx
        import json
        
        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system", 
                    "content": extraction_prompt["system_prompt"]
                },
                {
                    "role": "user", 
                    "content": extraction_prompt["main_prompt"]
                }
            ],
            "max_tokens": 4000,
            "temperature": 0.1,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "events": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string"},
                                        "description": {"type": "string"},
                                        "ai_summary": {"type": "string"},
                                        "start_date": {"type": "string"},
                                        "end_date": {"type": ["string", "null"]},
                                        "venue_name": {"type": "string"},
                                        "area": {"type": "string"},
                                        "min_price": {"type": "number"},
                                        "max_price": {"type": "number"},
                                        "family_friendly": {"type": "boolean"},
                                        "family_score": {"type": "number"},
                                        "primary_category": {"type": "string"},
                                        "source": {"type": "string"},
                                        "event_url": {"type": ["string", "null"]},
                                        "social_media": {
                                            "type": "object",
                                            "properties": {
                                                "instagram": {"type": ["string", "null"]},
                                                "facebook": {"type": ["string", "null"]},
                                                "twitter": {"type": ["string", "null"]},
                                                "tiktok": {"type": ["string", "null"]},
                                                "youtube": {"type": ["string", "null"]},
                                                "whatsapp": {"type": ["string", "null"]},
                                                "telegram": {"type": ["string", "null"]}
                                            }
                                        },
                                        "quality_metrics": {
                                            "type": "object",
                                            "properties": {
                                                "extraction_confidence": {"type": "number"},
                                                "data_completeness": {"type": "number"},
                                                "source_reliability": {"type": "string"},
                                                "last_verified": {"type": "string"},
                                                "extraction_method": {"type": "string"},
                                                "validation_warnings": {"type": "array", "items": {"type": "string"}}
                                            }
                                        }
                                    },
                                    "required": ["title", "description", "ai_summary", "start_date", "venue_name", "area", "family_friendly", "family_score", "primary_category", "source"]
                                }
                            },
                            "extraction_metadata": {
                                "type": "object",
                                "properties": {
                                    "total_events_found": {"type": "number"},
                                    "source_name": {"type": "string"},
                                    "processing_timestamp": {"type": "string"}
                                }
                            }
                        },
                        "required": ["events", "extraction_metadata"]
                    }
                }
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    perplexity_extractor.base_url,
                    headers={
                        "Authorization": f"Bearer {perplexity_extractor.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    
                    try:
                        if not content.strip().startswith('{'):
                            import re
                            json_match = re.search(r'\{.*\}', content, re.DOTALL)
                            if json_match:
                                content = json_match.group(0)
                            else:
                                logger.error(f"❌ No JSON found in response: {content}")
                                return {"events": [], "extraction_metadata": {"error": "No JSON in response"}}
                        
                        events_data = json.loads(content)
                        logger.info(f"✅ Successfully parsed {len(events_data.get('events', []))} events with sophisticated prompt")
                        return events_data
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Failed to parse JSON response: {e}")
                        return {"events": [], "extraction_metadata": {"error": "JSON parse error"}}
                        
                else:
                    logger.error(f"❌ Perplexity API error: {response.status_code} - {response.text}")
                    return {"events": [], "extraction_metadata": {"error": f"API error: {response.status_code}"}}
                    
        except Exception as e:
            logger.error(f"❌ Error during sophisticated parsing: {e}")
            return {"events": [], "extraction_metadata": {"error": str(e)}}

    def calculate_extraction_metrics(self, results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Calculate comprehensive metrics for the extraction session
        """
        total_events = sum(len(events) for events in results.values())
        
        # Source distribution
        source_distribution = {
            source: len(events) for source, events in results.items()
        }
        
        # Category analysis
        categories = {}
        family_scores = []
        
        for source_events in results.values():
            for event in source_events:
                category = event.get('primary_category', 'unknown')
                categories[category] = categories.get(category, 0) + 1
                
                if event.get('family_score', 0) > 0:
                    family_scores.append(event['family_score'])
        
        return {
            'extraction_timestamp': datetime.now().isoformat(),
            'total_events': total_events,
            'source_distribution': source_distribution,
            'category_distribution': categories,
            'family_events_count': len(family_scores),
            'average_family_score': sum(family_scores) / len(family_scores) if family_scores else 0,
            'extraction_method': 'firecrawl_mcp',
            'sources_processed': list(results.keys()),
            'success_rate': len([s for s in results.keys() if len(results[s]) > 0]) / len(results.keys())
        }

# Example usage and testing
async def main():
    """Test the Firecrawl MCP extractor"""
    logger.info("🧪 Testing Firecrawl MCP Extractor")
    
    extractor = FirecrawlMCPExtractor()
    
    # Test individual source extraction (limited for testing)
    logger.info("Testing individual source extraction...")
    platinumlist_events = await extractor.extract_from_source('platinumlist', limit=5)
    logger.info(f"Platinumlist events: {len(platinumlist_events)}")
    
    # Test all sources extraction (limited for testing)
    logger.info("Testing all sources extraction...")
    all_results = await extractor.extract_all_sources({'platinumlist': 3, 'timeout': 2, 'whatson': 2})
    
    # Calculate metrics
    metrics = extractor.calculate_extraction_metrics(all_results)
    logger.info(f"Extraction metrics: {json.dumps(metrics, indent=2)}")
    
    # Save sample results
    sample_output = {
        'extraction_summary': metrics,
        'sample_events': {
            source: events[:1] for source, events in all_results.items() if events
        }
    }
    
    output_file = Path("data/firecrawl_mcp_extraction_sample.json")
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(sample_output, f, indent=2, ensure_ascii=False)
    
    logger.info(f"💾 Sample results saved to {output_file}")
    
    return all_results

if __name__ == "__main__":
    asyncio.run(main())