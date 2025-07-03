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
            # Prepare event summaries with complete date information
            event_summaries = []
            for event in events[:15]:  # Max 15 events
                start_date = event.get("start_date")
                end_date = event.get("end_date")
                
                # Format dates for AI understanding
                start_date_str = str(start_date).split("T")[0] if start_date else ""
                end_date_str = str(end_date).split("T")[0] if end_date else ""
                
                # Create a clear date range description
                if start_date_str and end_date_str:
                    if start_date_str == end_date_str:
                        date_info = f"On {start_date_str}"
                    else:
                        date_info = f"From {start_date_str} to {end_date_str}"
                else:
                    date_info = start_date_str or "Date TBD"
                
                summary = {
                    "id": str(event.get("_id", "")),
                    "title": event.get("title", ""),
                    "start_date": start_date_str,
                    "end_date": end_date_str,
                    "date_range": date_info,
                    "category": event.get("category", ""),
                    "area": event.get("venue", {}).get("area", ""),
                    "family_score": event.get("familyScore", 0),
                    "price": event.get("pricing", {}).get("base_price", 0) if event.get("pricing") else "TBD",
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
6. BE ACCURATE: If the user searches for "this weekend" and you find events, do NOT say "no events this weekend"
7. BE SPECIFIC: Reference actual event titles and dates when summarizing

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
Current weekend: Saturday {(datetime.now() + timedelta(days=(5-datetime.now().weekday())%7)).strftime("%Y-%m-%d")} and Sunday {(datetime.now() + timedelta(days=(5-datetime.now().weekday())%7+1)).strftime("%Y-%m-%d")}

IMPORTANT: Events can match temporal queries in multiple ways:
1. Events that START during the requested period
2. Events that END during the requested period  
3. Events that SPAN/COVER the entire requested period (start before, end after)

For example, if someone searches "this weekend" (Saturday {(datetime.now() + timedelta(days=(5-datetime.now().weekday())%7)).strftime("%Y-%m-%d")} and Sunday {(datetime.now() + timedelta(days=(5-datetime.now().weekday())%7+1)).strftime("%Y-%m-%d")}):
- An event from 2025-01-01 to 2025-12-31 DOES match because it covers the weekend
- An event on Friday-Saturday DOES match because it ends during weekend  
- An event on Saturday-Monday DOES match because it starts during weekend

When users search with temporal keywords, consider ALL events that overlap:
- "today" = events that occur on or span {datetime.now().strftime("%Y-%m-%d")}
- "tomorrow" = events that occur on or span {(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")}
- "this weekend" = events that occur on or span the upcoming Saturday and Sunday
- "next weekend" = events that occur on or span the following Saturday and Sunday
- "this week" = events that occur during or span current Monday to Sunday
- "next week" = events that occur during or span next Monday to Sunday
- "this month" = events that occur during or span the current month
- "next month" = events that occur during or span the following month

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

IMPORTANT: When searching for "kids" or "children":
- EXCLUDE nightlife events (clubs, bars, adult shows)
- EXCLUDE events with age_min >= 18
- PREFER events with high familyScore (>70)
- PREFER events tagged as "family-friendly", "kids", "children"

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
- "kids weekend" = Must show ONLY kid-friendly events happening this weekend

AI RESPONSE GUIDELINES:
1. Count matching events: Start with "Found X events" or "No events found"
2. For temporal queries: Be specific about the date range you're checking
3. For kids queries: Emphasizes family-friendly nature of results
4. List 2-3 specific examples with titles and dates if events were found
5. If no exact matches: Explain what was missing and suggest alternatives
6. Keep response under 3 sentences, be concise and helpful

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
            
            # Calculate weekend dates for clarity
            days_until_saturday = (5 - now.weekday()) % 7
            if days_until_saturday == 0 and now.weekday() == 5:  # Already Saturday
                weekend_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif now.weekday() == 6:  # Sunday
                weekend_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
            else:
                weekend_start = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_until_saturday)
            weekend_end = weekend_start + timedelta(days=1)
            
            user_prompt = f"""Search Query: {query}
Current Date: {current_date}
Current Day of Week: {current_day_name}
Current Time: {current_time}
This Weekend: {weekend_start.strftime("%B %d")} - {weekend_end.strftime("%B %d, %Y")}

Database Events:
{json.dumps(event_summaries, indent=2)}

Please analyze the search query and find all matching events from the database provided above.

MATCHING INSTRUCTIONS:
1. Parse the search query to identify:
   - Temporal criteria (dates, times, days)
   - Price criteria (free, budget, specific amounts)
   - Location criteria (areas, venues)
   - Category/type criteria
   - Age/family criteria (CRITICAL for "kids" searches)
   - Any other specific requirements

2. For TEMPORAL queries, carefully check the date_range field:
   - If searching "this weekend" and an event shows "From 2025-01-01 to 2025-12-31", this DOES match because it spans the weekend
   - If searching "today" and an event shows "From 2025-07-01 to 2025-07-10", this DOES match if today falls within that range
   - Look at both start_date, end_date, and date_range to determine if events overlap with the requested time period

3. For KIDS/FAMILY queries:
   - Check family_score (prefer > 70)
   - Check tags for "family", "kids", "children"
   - EXCLUDE events with nightlife categories
   - EXCLUDE events with age restrictions 18+
   - Look for educational, cultural, arts categories

4. Match events by checking ALL relevant fields in the MongoDB schema
5. For compound queries, ALL criteria must match  
6. Consider partial text matches in title, description, and tags fields
7. Pay attention to event status - exclude cancelled events unless specifically requested
8. IMPORTANT: If you find events that match the criteria, do NOT say "no events found" - acknowledge the matches!

Generate an accurate AI response that:
- States the number of events found (or if none found)
- For temporal queries: Mentions the specific dates being searched
- For kids queries: Emphasizes family-friendly nature of results
- Lists 2-3 specific event examples if found
- Is helpful and accurate - don't claim "no events" if events exist

Return ONLY the JSON response, no additional text."""

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