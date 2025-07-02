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
        self.model = "gpt-4o-mini"  # Fast model
        
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
            
            # Single optimized prompt that does everything
            system_prompt = """You are an AI event assistant for Dubai. Analyze the query and score events in ONE response.

RESPOND WITH ONLY VALID JSON. No explanations or markdown.

Output format:
{
  "keywords": ["extracted", "keywords"],
  "time_period": "today/tomorrow/weekend/week/month/null",
  "date_from": "YYYY-MM-DD or null",
  "date_to": "YYYY-MM-DD or null", 
  "categories": ["relevant", "categories"],
  "family_friendly": true/false/null,
  "ai_response": "1-2 friendly sentences about results",
  "suggestions": ["4 related searches"],
  "scored_events": [
    {
      "id": "event_id",
      "score": 0-100,
      "reason": "1 sentence why it matches"
    }
  ]
}

Current date: """ + datetime.now().strftime("%Y-%m-%d (%A)")

            user_prompt = f"""Query: "{query}"

Events to score:
{json.dumps(event_summaries, indent=2)}

Analyze the query and score each event's relevance (0-100) based on:
- Keyword matches in title/description/tags
- Date/time alignment
- Category fit
- Family suitability if relevant
"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=800,  # Single call, optimized
                temperature=0.3  # Consistent results
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