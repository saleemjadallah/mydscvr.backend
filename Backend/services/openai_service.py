"""
OpenAI Service for intelligent search and event matching
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from openai import AsyncOpenAI
from pydantic import BaseModel

from config import Settings

logger = logging.getLogger(__name__)
settings = Settings()

class QueryAnalysis(BaseModel):
    """Structured analysis of user query"""
    intent: str
    time_period: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    categories: List[str] = []
    price_range: Optional[Dict[str, float]] = None
    age_group: Optional[str] = None
    family_friendly: Optional[bool] = None
    location_preferences: List[str] = []
    keywords: List[str] = []
    confidence: float = 0.0

class ScoredEvent(BaseModel):
    """Event with AI-generated relevance score and reasoning"""
    event_id: str
    score: float
    reasoning: str
    highlights: List[str] = []

class OpenAISearchService:
    """OpenAI-powered search service for intelligent event discovery"""
    
    def __init__(self):
        if not settings.openai_api_key:
            logger.warning("OpenAI API key not configured. AI search will be disabled.")
            self.enabled = False
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.enabled = True
            self.model = settings.openai_model
            self.max_tokens = settings.openai_max_tokens
            self.temperature = settings.openai_temperature
    
    async def analyze_query(self, query: str, user_context: Optional[Dict] = None) -> QueryAnalysis:
        """
        Analyze user query to extract intent, preferences, and search criteria
        """
        if not self.enabled:
            return QueryAnalysis(intent="general_search", keywords=[query])
        
        try:
            system_prompt = """You are an expert event discovery assistant for Dubai. Analyze user queries to extract search intent and preferences.

Return a JSON object with these fields:
- intent: main search purpose (weekend_activities, date_night, family_fun, cultural_experience, dining, entertainment, outdoor_adventure, indoor_activities, free_events, luxury_experience)
- time_period: when they want to attend (today, tomorrow, this_weekend, next_weekend, this_week, next_week, this_month, next_month, flexible)
- date_from: start date if specific (YYYY-MM-DD format)
- date_to: end date if specific (YYYY-MM-DD format)
- categories: relevant event categories (dining, entertainment, cultural, outdoor_activities, kids_activities, etc.)
- price_range: {"min": number, "max": number} if mentioned
- age_group: target age (toddlers, kids, teenagers, adults, seniors, all_ages)
- family_friendly: true/false if family suitability is important
- location_preferences: Dubai areas mentioned (Downtown, Marina, JBR, etc.)
- keywords: important search terms
- confidence: how confident you are in this analysis (0.0-1.0)

Current date context: Today is """ + datetime.now().strftime("%Y-%m-%d (%A)")
            
            user_prompt = f"User query: '{query}'"
            if user_context:
                user_prompt += f"\nUser context: {json.dumps(user_context)}"
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            result = json.loads(response.choices[0].message.content)
            return QueryAnalysis(**result)
            
        except Exception as e:
            logger.error(f"OpenAI query analysis failed: {e}")
            # Return basic analysis as fallback
            return QueryAnalysis(
                intent="general_search",
                keywords=query.split(),
                confidence=0.1
            )
    
    async def match_events(self, query: str, events: List[Dict], analysis: QueryAnalysis) -> List[ScoredEvent]:
        """
        Use OpenAI to intelligently match events to user query
        """
        if not self.enabled or not events:
            return []
        
        try:
            # Prepare event data for AI analysis (limit to essential fields to save tokens)
            event_summaries = []
            for event in events[:20]:  # Limit to prevent token overflow
                summary = {
                    "id": str(event.get("id", "")),
                    "title": event.get("title", ""),
                    "description": (event.get("description", "") or "")[:200],  # Truncate description
                    "category": event.get("category", ""),
                    "tags": event.get("tags", [])[:5],  # Limit tags
                    "venue": {
                        "name": event.get("venue", {}).get("name", ""),
                        "area": event.get("venue", {}).get("area", "")
                    },
                    "price": event.get("price", {}),
                    "family_score": event.get("family_score"),
                    "start_date": event.get("start_date", ""),
                    "age_range": event.get("age_range", "")
                }
                event_summaries.append(summary)
            
            system_prompt = """You are an expert event curator for Dubai. Score how well each event matches the user's query and intent.

For each event, provide:
- score: relevance score from 0-100
- reasoning: 1-2 sentences explaining why this event matches (or doesn't match)
- highlights: 2-3 key points that make this event appealing for this query

Return JSON array of objects with: {"event_id": "...", "score": number, "reasoning": "...", "highlights": ["...", "..."]}

Consider:
- Query intent and user preferences
- Event timing relative to user's time preferences
- Price fit for user's budget hints
- Family suitability if mentioned
- Location convenience
- Activity type alignment
- Special features or unique aspects

Be honest about scoring - not every event needs to be highly scored."""

            user_prompt = f"""
User Query: "{query}"
Analysis: {analysis.dict()}

Events to score:
{json.dumps(event_summaries, indent=2)}
"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=2000,  # More tokens for event scoring
                temperature=0.2  # Lower temperature for more consistent scoring
            )
            
            results = json.loads(response.choices[0].message.content)
            scored_events = [ScoredEvent(**result) for result in results]
            
            # Sort by score descending
            scored_events.sort(key=lambda x: x.score, reverse=True)
            
            return scored_events
            
        except Exception as e:
            logger.error(f"OpenAI event matching failed: {e}")
            # Return basic scoring as fallback
            return [
                ScoredEvent(
                    event_id=str(event.get("id", "")),
                    score=50.0,
                    reasoning="Event available in Dubai",
                    highlights=["Local activity"]
                ) for event in events
            ]
    
    async def generate_response(self, query: str, scored_events: List[ScoredEvent], analysis: QueryAnalysis) -> str:
        """
        Generate conversational AI response about the search results
        """
        if not self.enabled:
            return f"I found {len(scored_events)} events matching '{query}'. Check them out below!"
        
        try:
            # Get top events for response generation
            top_events = scored_events[:5]
            
            system_prompt = """You are a friendly, knowledgeable Dubai events concierge. Generate an engaging, helpful response about the search results.

Style:
- Conversational and enthusiastic
- 2-3 sentences maximum
- Highlight the best matches
- Include practical tips if relevant
- Mention variety if applicable

Avoid:
- Generic responses
- Overly promotional language
- Listing event names (let the results speak)
- Being repetitive"""

            user_prompt = f"""
User searched for: "{query}"
Query analysis: {analysis.dict()}

Top matching events (scores):
{json.dumps([{"score": e.score, "reasoning": e.reasoning, "highlights": e.highlights} for e in top_events], indent=2)}

Generate a personalized response about these search results.
"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=200,
                temperature=0.7  # More creative for response generation
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"OpenAI response generation failed: {e}")
            # Return fallback response
            event_count = len(scored_events)
            if event_count == 0:
                return f"I couldn't find events specifically matching '{query}', but Dubai has many amazing activities to explore!"
            else:
                return f"Perfect! I found {event_count} great options for '{query}'. Dubai offers incredible experiences for every interest!"
    
    async def suggest_followups(self, query: str, analysis: QueryAnalysis, found_events: int) -> List[str]:
        """
        Generate intelligent follow-up search suggestions
        """
        if not self.enabled:
            return [
                "Indoor activities",
                "Family events",
                "Weekend activities",
                "Free events"
            ]
        
        try:
            system_prompt = """Generate 4-6 helpful follow-up search suggestions based on the user's query and what they found.

Suggestions should:
- Be related but explore different angles
- Include timing variations if relevant
- Suggest price alternatives
- Offer category expansions
- Be actionable search phrases

Return as JSON array of strings."""

            user_prompt = f"""
Original query: "{query}"
Analysis: {analysis.dict()}
Events found: {found_events}

Generate follow-up suggestions.
"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=300,
                temperature=0.6
            )
            
            suggestions = json.loads(response.choices[0].message.content)
            return suggestions[:6]  # Limit to 6 suggestions
            
        except Exception as e:
            logger.error(f"OpenAI followup generation failed: {e}")
            # Return contextual fallbacks
            if analysis.intent == "weekend_activities":
                return ["Next weekend activities", "Indoor weekend fun", "Family weekend events", "Free weekend activities"]
            elif analysis.intent == "family_fun":
                return ["Kids activities", "Indoor family fun", "Educational events", "Free family events"]
            else:
                return ["This weekend", "Indoor activities", "Family events", "Free events"]

# Global instance
openai_service = OpenAISearchService()