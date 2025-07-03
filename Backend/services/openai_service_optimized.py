"""
Optimized OpenAI service that combines all AI operations into a single call
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from openai import AsyncOpenAI
import httpx
from pydantic import BaseModel
from config import settings

logger = logging.getLogger(__name__)

class OptimizedQueryAnalysis(BaseModel):
    """Combined analysis result from single AI call"""
    # Query understanding
    keywords: List[str]
    time_period: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    categories: List[str] = []
    family_friendly: Optional[bool] = None
    
    # Response generation
    ai_response: str
    suggestions: List[str]
    
    # Event scoring (populated separately)
    scored_events: List[Dict[str, Any]] = []

class OptimizedOpenAIService:
    """Optimized service that makes a single AI call for all operations"""
    
    def __init__(self):
        self.enabled = bool(settings.openai_api_key)
        self.client = None
        
        # Configuration as per advanced requirements
        self.model = "gpt-4o-mini"  # Cost-effective, fast, good for search tasks
        self.temperature = 0.3      # Lower temperature for more consistent results
        self.max_tokens = 1500      # Increased for complex queries
        self.top_p = 0.9           # Slightly focused responses
        self.frequency_penalty = 0.0
        self.presence_penalty = 0.0
        
        if self.enabled:
            try:
                self.client = AsyncOpenAI(
                    api_key=settings.openai_api_key,
                    timeout=httpx.Timeout(30.0)
                )
                logger.info(f"✅ Optimized OpenAI service initialized with model: {self.model}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.enabled = False
    
    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """Extract JSON from OpenAI response"""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to find JSON in various formats
            patterns = [
                r'```json\s*({.*?})\s*```',
                r'```\s*({.*?})\s*```',
                r'({[^{}]*(?:{[^{}]*}[^{}]*)*})',
            ]
            
            for pattern in patterns:
                matches = re.search(pattern, response_text, re.DOTALL)
                if matches:
                    try:
                        return json.loads(matches.group(1))
                    except json.JSONDecodeError:
                        continue
            
            # Last resort: find first { to last }
            start = response_text.find('{')
            end = response_text.rfind('}')
            if start != -1 and end != -1:
                try:
                    return json.loads(response_text[start:end+1])
                except json.JSONDecodeError:
                    pass
                    
            raise ValueError(f"Could not extract JSON from response: {response_text[:200]}...")
    
    async def analyze_and_score(self, query: str, events: List[Dict]) -> OptimizedQueryAnalysis:
        """
        Single AI call that analyzes query AND scores events
        """
        if not self.enabled:
            return OptimizedQueryAnalysis(
                keywords=[query],
                ai_response=f"Found {len(events)} events matching '{query}'",
                suggestions=["Family events", "Weekend activities", "Indoor fun"],
                scored_events=[]
            )
        
        try:
            # Prepare event summaries (keep it minimal for speed)
            event_summaries = []
            for event in events[:15]:  # Max 15 events
                summary = {
                    "id": str(event.get("_id", "")),
                    "title": event.get("title", ""),
                    "date": str(event.get("start_date", "")).split("T")[0] if event.get("start_date") else "",
                    "category": event.get("category", ""),
                    "area": event.get("venue", {}).get("area", ""),
                    "family_score": event.get("familyScore", 0),
                    "tags": event.get("tags", [])[:3],  # First 3 tags only
                    "description_snippet": (event.get("description", "") or "")[:100]
                }
                event_summaries.append(summary)
            
            # Advanced system prompt with comprehensive MongoDB schema understanding
            system_prompt = f"""You are an intelligent search assistant for a Dubai events database. Your role is to analyze user search queries and match them with relevant events from the provided MongoDB collection data.

CRITICAL RULES:
1. You MUST ONLY reference events that exist in the provided data
2. Never invent, hallucinate, or reference events not in the database
3. If no events match the search criteria, clearly state that no matching events were found
4. Always cite the specific event IDs when referencing events
5. Consider all available fields in the MongoDB schema when matching

MONGODB SCHEMA UNDERSTANDING:
Events in the database have these fields:
- _id: MongoDB ObjectId
- title: Event name
- description: Full event description
- category/primary_category: Main event type (arts, music, sports, dining, nightlife, cultural)
- secondary_categories: Additional categories array
- start_date/end_date: DateTime fields for event timing
- price: Text description ("Free", "100 AED", "50-200 AED")
- pricing.base_price/pricing.max_price: Numeric price values
- venue.name/venue.area: Location information
- venue.coordinates: GPS location {{lat, lng}}
- familyScore: Family suitability score (0-100)
- is_family_friendly: Boolean flag
- age_min/age_max/age_group/age_restrictions: Age-related fields
- tags: Array of keywords
- status: Event status (active, cancelled, postponed)

TEMPORAL SEARCH UNDERSTANDING:
Today's date is: {datetime.now().strftime("%Y-%m-%d (%A)")}

When users search with temporal keywords, interpret them as follows:
- "today" = events where start_date is on {datetime.now().strftime("%Y-%m-%d")}
- "tomorrow" = events where start_date is on {(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")}
- "this weekend" = events on the upcoming Saturday and Sunday
- "next weekend" = events on the following Saturday and Sunday
- "this week" = events from current Monday to Sunday
- "next week" = events from next Monday to Sunday
- "this month" = all events in the current month
- "next month" = all events in the following month
- "tonight" = events today with start_date after 6 PM
- "this morning" = events today with start_date before 12 PM
- "this afternoon" = events today with start_date between 12 PM and 6 PM

PRICE & COST UNDERSTANDING:
When users search with price-related keywords:
- "free" or "free events" = events where price contains "Free" OR pricing.base_price = 0 OR price = "0"
- "cheap" or "budget" or "affordable" = events where pricing.base_price <= 50
- "under X" or "less than X" = events where pricing.base_price < X
- "around X" = events where pricing.base_price <= X*1.2 AND pricing.max_price >= X*0.8
- "expensive" or "premium" or "luxury" = events where pricing.base_price > 200

LOCATION UNDERSTANDING:
Recognize Dubai areas and match against venue.area field:
- "Downtown" includes: Downtown Dubai, Dubai Mall, Burj Khalifa area
- "Marina" includes: Dubai Marina, Marina Walk, Marina Mall
- "JBR" includes: Jumeirah Beach Residence, The Beach, The Walk
- "Business Bay" includes: Business Bay area
- "DIFC" includes: Dubai International Financial Centre
- "Jumeirah" includes: Jumeirah Beach, Jumeirah Road
- "Deira" includes: Old Dubai, Gold Souk area

FAMILY & AGE UNDERSTANDING:
- "family events" or "family-friendly" = is_family_friendly = true OR familyScore > 70
- "kids events" or "children activities" = age_min < 12 OR tags include "children"
- "adult only" or "adults only" = age_min >= 18 OR age_restrictions contains "18+"
- "toddler friendly" = age_min <= 3
- "teen events" = suitable for ages 13-17

CATEGORY UNDERSTANDING:
Map user queries to primary_category and secondary_categories:
- "things to do" = any category
- "entertainment" = music, arts, nightlife, cultural events
- "outdoor activities" = events where venue_type = "outdoor" OR indoor_outdoor = "outdoor"
- "indoor activities" = events where venue_type = "indoor" OR indoor_outdoor = "indoor"
- "workshops" or "classes" = event_type = "workshop" OR category = "educational"
- "festivals" = event_type = "festival"
- "concerts" or "music" = category = "music" OR event_type = "concert"
- "sports" or "fitness" = category = "sports"
- "art" or "exhibitions" = category = "arts" OR event_type = "exhibition"

COMBINED QUERY UNDERSTANDING:
Handle multiple criteria in single queries:
- "free weekend family events" = Combine temporal + price + family filters
- "outdoor activities in Marina" = Combine venue_type + location filters
- "cheap things to do tomorrow night" = Combine price + temporal + time filters

RESPOND WITH ONLY VALID JSON matching this exact format:
{{
  "keywords": ["extracted", "keywords"],
  "time_period": "today/tomorrow/weekend/week/month/null",
  "date_from": "YYYY-MM-DD or null",
  "date_to": "YYYY-MM-DD or null",
  "categories": ["relevant", "categories"],
  "family_friendly": true/false/null,
  "ai_response": "Brief summary of search results",
  "suggestions": ["4 related search suggestions"],
  "scored_events": [
    {{
      "id": "event_id_from_database",
      "score": 0-100,
      "reason": "Brief explanation of why this event matches"
    }}
  ]
}}"""

            # Enhanced user prompt template with current date/time context
            now = datetime.now()
            current_date = now.strftime("%Y-%m-%d")
            current_day_name = now.strftime("%A")
            current_time = now.strftime("%H:%M")
            
            user_prompt = f"""Search Query: {query}
Current Date: {current_date}
Current Day of Week: {current_day_name}
Current Time: {current_time}

Database Events:
{json.dumps(event_summaries, indent=2)}

Please analyze the search query and find all matching events from the database provided above.

MATCHING INSTRUCTIONS:
1. Parse the search query to identify:
   - Temporal criteria (dates, times, days)
   - Price criteria (free, budget, specific amounts)
   - Location criteria (areas, venues)
   - Category/type criteria
   - Age/family criteria
   - Any other specific requirements

2. Match events by checking ALL relevant fields in the MongoDB schema
3. For compound queries, ALL criteria must match
4. Consider partial text matches in title, description, and tags fields
5. Pay attention to event status - exclude cancelled events unless specifically requested

Return your response in the following format:

1. SEARCH INTERPRETATION: 
   - What the user is looking for
   - Identified criteria: temporal, price, location, category, age group
   - Any ambiguities or assumptions made

2. FILTER CALCULATION:
   - Date range: [if applicable]
   - Price range: [if applicable]
   - Location filter: [if applicable]
   - Category filter: [if applicable]
   - Age filter: [if applicable]

3. MATCHING EVENTS: List all events that match with:
   - Event ID (_id)
   - Event Title
   - Date/Time (formatted nicely)
   - Price (show actual price or range)
   - Location (venue.name, venue.area)
   - Family Score (if relevant to query)
   - Match Score (1-10)
   - Match Reason (explain which criteria matched)

4. SUMMARY: A concise 2-3 sentence summary highlighting:
   - Number of events found
   - Key characteristics of the results
   - Any notable patterns or recommendations

5. NO MATCHES: If no events match:
   - Explain which criteria couldn't be satisfied
   - Suggest query modifications
   - List closest alternatives if any exist

Remember: Only reference events that exist in the provided database data. Return ONLY the JSON response, no additional text."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                frequency_penalty=self.frequency_penalty,
                presence_penalty=self.presence_penalty
            )
            
            raw_content = response.choices[0].message.content
            logger.debug(f"Optimized AI response: {raw_content[:200]}...")
            
            result = self._extract_json_from_response(raw_content)
            
            # Ensure all required fields
            return OptimizedQueryAnalysis(
                keywords=result.get("keywords", [query]),
                time_period=result.get("time_period"),
                date_from=result.get("date_from"),
                date_to=result.get("date_to"),
                categories=result.get("categories", []),
                family_friendly=result.get("family_friendly"),
                ai_response=result.get("ai_response", f"Found {len(events)} events for '{query}'"),
                suggestions=result.get("suggestions", ["Weekend events", "Family activities"]),
                scored_events=result.get("scored_events", [])
            )
            
        except Exception as e:
            logger.error(f"Optimized AI analysis failed: {e}")
            # Return basic fallback
            return OptimizedQueryAnalysis(
                keywords=[query],
                ai_response=f"Found {len(events)} events matching your search",
                suggestions=["Try different dates", "Explore categories", "Family events"],
                scored_events=[{"id": str(e.get("_id", "")), "score": 50, "reason": "Potential match"} for e in events[:10]]
            )

# Global instance
optimized_openai_service = OptimizedOpenAIService()