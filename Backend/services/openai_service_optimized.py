"""
Optimized OpenAI service that combines all AI operations into a single call
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
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
        
        # Configuration as per requirements
        self.model = "gpt-4o-mini"  # Cost-effective, fast, good for search tasks
        self.temperature = 0.3      # Lower temperature for more consistent results
        self.max_tokens = 1000      # Adjust based on your needs
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
            
            # System prompt as per requirements
            system_prompt = """You are an intelligent search assistant for an events database. Your role is to analyze user search queries and match them with relevant events from the provided MongoDB collection data.

CRITICAL RULES:
1. You MUST ONLY reference events that exist in the provided data
2. Never invent, hallucinate, or reference events not in the database
3. If no events match the search criteria, clearly state that no matching events were found
4. Always cite the specific event IDs when referencing events

Your tasks:
1. Analyze the user's search keywords and intent
2. Identify all relevant events from the provided database entries
3. Provide a concise summary of matching events
4. Rank results by relevance to the search query

When matching events, consider:
- Event titles and descriptions
- Event categories or types
- Dates and times
- Locations
- Tags or keywords
- Any other relevant fields in your schema

Current date: """ + datetime.now().strftime("%Y-%m-%d (%A)") + """

RESPOND WITH ONLY VALID JSON matching this exact format:
{
  "keywords": ["extracted", "keywords"],
  "time_period": "today/tomorrow/weekend/week/month/null",
  "date_from": "YYYY-MM-DD or null",
  "date_to": "YYYY-MM-DD or null",
  "categories": ["relevant", "categories"],
  "family_friendly": true/false/null,
  "ai_response": "Brief summary of search results",
  "suggestions": ["4 related search suggestions"],
  "scored_events": [
    {
      "id": "event_id_from_database",
      "score": 0-100,
      "reason": "Brief explanation of why this event matches"
    }
  ]
}"""

            # User prompt template as per requirements
            user_prompt = f"""Search Query: {query}

Database Events:
{json.dumps(event_summaries, indent=2)}

Please analyze the search query and find all matching events from the database provided above. Return your response in the following format:

1. SEARCH INTERPRETATION: Brief explanation of what you understood the user is looking for

2. MATCHING EVENTS: List all events that match the search criteria with:
   - Event ID
   - Event Title
   - Relevance Score (1-100)
   - Brief explanation of why this event matches

3. SUMMARY: A 2-3 sentence summary of the search results

4. NO MATCHES: If no events match, explain why and suggest how the user might refine their search

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