import json
from datetime import datetime
import httpx

class DubaiEventsPerplexityExtractor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.perplexity.ai"
    
    def create_enhanced_prompt(self, content: str, source_name: str) -> dict:
        """
        Create an enhanced prompt for extracting Dubai family event data
        """
        
        system_prompt = """You are a Dubai Events Data Extraction specialist. 
        You excel at extracting ALL types of events in Dubai and understanding Dubai's unique cultural context.
        You extract comprehensive event data and provide family suitability analysis as metadata.
        You always return valid JSON and calculate accurate family suitability scores for filtering purposes."""
        
        main_prompt = f"""
TASK: Extract ALL events from the provided {source_name} content - including nightlife, business, cultural, sports, dining, entertainment, and family events.

CONTEXT: This is for a comprehensive Dubai events platform. Extract every event you can find, regardless of target audience. 
We'll use family scoring and filtering on the frontend, but the database should contain ALL Dubai events.

CONTENT TO ANALYZE:
{content}

EXTRACTION REQUIREMENTS:
Return a JSON object with an "events" array containing ALL event information found.

For each event, extract:

1. BASIC INFORMATION:
   - title: Clear, family-friendly event name
   - description: Original full description from source
   - ai_summary: Create a 100-150 character family-focused summary highlighting what makes it special for families

2. DATE & TIME:
   - start_date: ISO format (YYYY-MM-DDTHH:MM:SS)
   - end_date: ISO format (if available, null if not)
   - duration_hours: Estimated duration (1-8 hours)
   - recurring: true/false if it's a recurring event

3. VENUE DETAILS:
   - venue_name: Official venue name
   - address: Full address if available
   - area: Dubai area (Dubai Marina, JBR, Downtown, DIFC, etc.)
   - venue_type: indoor/outdoor/both
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
   - child_activity_level: "passive", "low", "medium", "high" (how active children need to be)

6. EVENT CATEGORIZATION:
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

7. ACCESSIBILITY & LOGISTICS:
   - special_needs_friendly: true/false/unknown
   - language_requirements: "arabic", "english", "bilingual", "multilingual", "none"
   - transportation_notes: Any specific transport information
   - alcohol_served: true/false/unknown (important for cultural considerations)

8. FAMILY SCORE CALCULATION (0-100, for frontend filtering):
   Calculate ONLY if family_friendly is true, otherwise set to 0:
   - Age inclusivity: Wider child age range = higher score
   - Safety & supervision: Supervised, stroller-accessible = higher score
   - Educational value: Learning opportunities = higher score
   - Duration: 1-4 hours ideal for families = higher score
   - Venue accessibility: Metro accessible, parking = higher score
   - Pricing: Free or reasonable pricing = higher score
   - Time: Weekend or evening timing = higher score
   
   For non-family events (nightlife, 18+ events, etc.), always set family_score to 0.

8. METADATA:
   - source: "{source_name}"
   - source_url: Original event URL if available
   - scraped_at: Current timestamp
   - image_urls: Array of image URLs if found
   - booking_required: true/false
   - contact_info: Phone/email if available
   - ticket_links: Array of booking/ticket URLs
   - social_media: {{instagram, facebook, twitter handles if found}}

EXTRACTION STANDARDS:
- Extract ALL events found in the content, regardless of audience
- Include nightlife, business events, dining experiences, cultural events, sports, entertainment - everything
- Don't filter out adult-only events - mark them appropriately with family_friendly: false
- Include events without clear dates but mark them appropriately  
- Extract partial information rather than skipping events
- For unclear information, use "unknown" rather than guessing

RESPONSE FORMAT:
Return ONLY valid JSON in this exact structure:
{{
  "events": [
    {{
      "title": "Rooftop Jazz Night at Address Downtown",
      "description": "Premium jazz evening featuring international artists with cocktails and city views. Smart casual dress code required.",
      "ai_summary": "Sophisticated jazz night with cocktails & Dubai skyline views at Address Downtown - adults only premium experience",
      "start_date": "2025-06-15T20:00:00",
      "end_date": "2025-06-16T01:00:00", 
      "duration_hours": 5,
      "recurring": true,
      "venue_name": "Address Downtown Rooftop",
      "address": "Downtown Dubai",
      "area": "Downtown",
      "venue_type": "indoor",
      "parking_available": true,
      "metro_accessible": true,
      "min_price": 250,
      "max_price": 500,
      "currency": "AED",
      "free_for_children": false,
      "pricing_notes": "Includes 2 drinks, food separate",
      "target_audience": ["adults", "couples", "professionals"],
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
      "secondary_categories": ["music", "dining", "entertainment"],
      "event_type": "concert",
      "indoor_outdoor": "indoor",
      "special_occasion": "weekend",
      "special_needs_friendly": unknown,
      "language_requirements": "english",
      "transportation_notes": "Valet parking available",
      "alcohol_served": true,
      "family_score": 0,
      "source": "{source_name}",
      "source_url": "https://example.com/event",
      "scraped_at": "{datetime.now().isoformat()}",
      "image_urls": ["https://example.com/image.jpg"],
      "booking_required": true,
      "contact_info": "reservations@address.com",
      "ticket_links": ["https://tickets.com/jazz-night"],
      "social_media": {{"instagram": "@addressdowntown"}}
    }},
    {{
      "title": "Kids Science Workshop at Dubai Mall",
      "description": "Interactive science experiments for children aged 6-12. Professional educators guide hands-on learning activities.",
      "ai_summary": "Interactive science experiments & hands-on learning for kids 6-12 at Dubai Mall - educational fun with professional guides",
      "start_date": "2025-06-16T14:00:00",
      "end_date": "2025-06-16T16:00:00",
      "duration_hours": 2,
      "recurring": false,
      "venue_name": "Dubai Mall Science Center",
      "address": "Downtown Dubai",
      "area": "Downtown", 
      "venue_type": "indoor",
      "parking_available": true,
      "metro_accessible": true,
      "min_price": 120,
      "max_price": 120,
      "currency": "AED",
      "free_for_children": false,
      "pricing_notes": "Per child, parent entry free",
      "target_audience": ["children", "families"],
      "age_restrictions": "6-12 years",
      "dress_code": "casual",
      "family_friendly": true,
      "child_age_min": 6,
      "child_age_max": 12,
      "stroller_accessible": true,
      "requires_supervision": true,
      "educational_value": "high",
      "child_activity_level": "medium",
      "primary_category": "educational",
      "secondary_categories": ["children", "workshops", "family"],
      "event_type": "workshop",
      "indoor_outdoor": "indoor",
      "special_occasion": null,
      "special_needs_friendly": true,
      "language_requirements": "bilingual",
      "transportation_notes": null,
      "alcohol_served": false,
      "family_score": 88,
      "source": "{source_name}",
      "source_url": "https://example.com/event2",
      "scraped_at": "{datetime.now().isoformat()}",
      "image_urls": [],
      "booking_required": true,
      "contact_info": "science@dubaimall.com",
      "ticket_links": ["https://dubaimall.com/science-workshop"],
      "social_media": {{"instagram": "@dubaimall"}}
    }}
  ],
  "extraction_metadata": {{
    "total_events_found": 2,
    "family_events_count": 1,
    "adult_events_count": 1,
    "source_processed": "{source_name}",
    "processing_timestamp": "{datetime.now().isoformat()}",
    "content_quality": "high"
  }}
}}

IMPORTANT: 
- Extract ALL events regardless of target audience
- Use family_friendly and family_score for filtering capabilities
- Return ONLY the JSON response, no additional text
- Ensure all dates are in correct ISO format
- Family scores should only be calculated for family_friendly events
- Include metadata counts for different event types
"""
        
        return {
            "system_prompt": system_prompt,
            "main_prompt": main_prompt
        }
    
    async def extract_events(self, content: str, source_name: str) -> dict:
        """
        Send content to Perplexity API for event extraction
        """
        prompts = self.create_enhanced_prompt(content, source_name)
        
        payload = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {
                    "role": "system", 
                    "content": prompts["system_prompt"]
                },
                {
                    "role": "user", 
                    "content": prompts["main_prompt"]
                }
            ],
            "max_tokens": 4000,
            "temperature": 0.1,  # Low temperature for consistent extraction
            "response_format": {"type": "json_object"}
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                return json.loads(content)
            else:
                raise Exception(f"Perplexity API error: {response.status_code} - {response.text}")

# Example usage
async def main():
    extractor = DubaiEventsPerplexityExtractor("your-perplexity-api-key")
    
    # Sample content from TimeOut Dubai
    sample_content = """
    <div class="event-card">
        <h2>Summer Kids Workshop at Dubai Mall</h2>
        <p>Join us every Saturday for creative arts and crafts workshops designed for children aged 5-12. 
        Professional instructors will guide kids through painting, pottery, and jewelry making activities.</p>
        <div class="event-details">
            <span class="date">Every Saturday, 2:00 PM - 5:00 PM</span>
            <span class="venue">Dubai Mall Activity Center</span>
            <span class="price">AED 150 per child</span>
        </div>
    </div>
    """
    
    try:
        events_data = await extractor.extract_events(sample_content, "TimeOut Dubai")
        print(json.dumps(events_data, indent=2))
        
        # Validate the results
        for event in events_data.get("events", []):
            print(f"✅ Extracted: {event['title']} (Family Score: {event['family_score']})")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())