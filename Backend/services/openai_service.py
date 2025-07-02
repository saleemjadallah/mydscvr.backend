"""
OpenAI Service for intelligent search and event matching
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
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
    
    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """Extract JSON from OpenAI response, handling various formats"""
        try:
            # First try direct parsing
            return json.loads(response_text)
        except json.JSONDecodeError:
            logger.debug(f"Direct JSON parsing failed. Raw response: {response_text[:500]}...")
            
            # Try to find JSON within code blocks or other formatting
            json_patterns = [
                r'```json\s*({.*?})\s*```',  # JSON in code blocks
                r'```\s*({.*?})\s*```',      # JSON in plain code blocks
                r'({\s*".*?})',              # Standalone JSON objects
                r'\[\s*{.*?}\s*\]'           # JSON arrays
            ]
            
            for pattern in json_patterns:
                matches = re.search(pattern, response_text, re.DOTALL | re.MULTILINE)
                if matches:
                    try:
                        json_str = matches.group(1) if matches.lastindex else matches.group(0)
                        return json.loads(json_str)
                    except (json.JSONDecodeError, IndexError):
                        continue
            
            # If all patterns fail, try to extract anything that looks like JSON
            # Find the first { and last } and try parsing that
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                try:
                    potential_json = response_text[start_idx:end_idx + 1]
                    return json.loads(potential_json)
                except json.JSONDecodeError:
                    pass
            
            # Last resort: look for array format
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                try:
                    potential_json = response_text[start_idx:end_idx + 1]
                    return json.loads(potential_json)
                except json.JSONDecodeError:
                    pass
                    
            logger.error(f"Failed to extract JSON from response: {response_text}")
            raise json.JSONDecodeError("Could not extract valid JSON from response", response_text, 0)
    
    async def analyze_query(self, query: str, user_context: Optional[Dict] = None) -> QueryAnalysis:
        """
        Analyze user query to extract intent, preferences, and search criteria
        """
        if not self.enabled:
            return QueryAnalysis(intent="general_search", keywords=[query])
        
        try:
            system_prompt = """You are an expert event discovery assistant for Dubai. Analyze user queries to extract search intent and preferences.

IMPORTANT: You must respond with ONLY a valid JSON object. Do not include any explanation, markdown formatting, or additional text.

Return a JSON object with these exact fields:
- intent: main search purpose (weekend_activities, date_night, family_fun, cultural_experience, dining, entertainment, outdoor_adventure, indoor_activities, free_events, luxury_experience)
- time_period: when they want to attend (today, tomorrow, this_weekend, next_weekend, this_week, next_week, this_month, next_month, flexible)
- date_from: start date if specific (YYYY-MM-DD format) or null
- date_to: end date if specific (YYYY-MM-DD format) or null
- categories: array of relevant event categories (dining, entertainment, cultural, outdoor_activities, kids_activities, etc.)
- price_range: {"min": number, "max": number} object if mentioned, or null
- age_group: target age (toddlers, kids, teenagers, adults, seniors, all_ages) or null
- family_friendly: true/false if family suitability is important, or null
- location_preferences: array of Dubai areas mentioned (Downtown, Marina, JBR, etc.)
- keywords: array of important search terms
- confidence: how confident you are in this analysis (0.0-1.0)

Current date context: Today is """ + datetime.now().strftime("%Y-%m-%d (%A)") + """

Example response format:
{"intent": "family_fun", "time_period": "this_weekend", "date_from": null, "date_to": null, "categories": ["kids_activities"], "price_range": null, "age_group": "kids", "family_friendly": true, "location_preferences": [], "keywords": ["family", "fun"], "confidence": 0.8}"""
            
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
            
            raw_content = response.choices[0].message.content
            logger.debug(f"OpenAI query analysis raw response: {raw_content}")
            
            result = self._extract_json_from_response(raw_content)
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
            # Reduce to 10 events for faster processing
            for event in events[:10]:  # Limit to prevent token overflow and speed up processing
                # Convert datetime to string if necessary
                start_date = event.get("start_date", "")
                if isinstance(start_date, datetime):
                    start_date = start_date.isoformat()
                
                summary = {
                    "id": str(event.get("_id", event.get("id", ""))),  # Handle both _id and id
                    "title": event.get("title", ""),
                    "description": (event.get("description", "") or "")[:200],  # Truncate description
                    "category": event.get("category", ""),
                    "tags": event.get("tags", [])[:5],  # Limit tags
                    "venue": {
                        "name": event.get("venue", {}).get("name", ""),
                        "area": event.get("venue", {}).get("area", "")
                    },
                    "price": event.get("pricing", event.get("price", {})),  # Handle both pricing and price fields
                    "family_score": event.get("familyScore", event.get("family_score")),  # Handle both camelCase and snake_case
                    "start_date": start_date,
                    "age_range": event.get("age_range", "")
                }
                event_summaries.append(summary)
            
            system_prompt = """You are an expert event curator for Dubai. Score how well each event matches the user's query and intent.

IMPORTANT: You must respond with ONLY a valid JSON array. Do not include any explanation, markdown formatting, or additional text.

For each event, provide:
- event_id: the event ID as a string
- score: relevance score from 0-100 (number)
- reasoning: 1-2 sentences explaining why this event matches
- highlights: array of 2-3 key points that make this event appealing

Return a JSON array of objects with this exact format:
[{"event_id": "string", "score": number, "reasoning": "string", "highlights": ["string", "string"]}]

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
Analysis: {analysis.model_dump()}

Events to score:
{json.dumps(event_summaries, indent=2)}
"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1500,  # Reduced tokens for faster processing
                temperature=0.2  # Lower temperature for more consistent scoring
            )
            
            raw_content = response.choices[0].message.content
            logger.debug(f"OpenAI event scoring raw response: {raw_content}")
            
            results = self._extract_json_from_response(raw_content)
            # Handle both single dict and list of dicts
            if isinstance(results, dict):
                results = [results]
            elif not isinstance(results, list):
                logger.error(f"Unexpected result type: {type(results)}")
                raise ValueError(f"Expected list or dict, got {type(results)}")
            
            scored_events = []
            for result in results:
                try:
                    scored_events.append(ScoredEvent(**result))
                except Exception as e:
                    logger.warning(f"Failed to create ScoredEvent from {result}: {e}")
                    continue
            
            # Sort by score descending
            scored_events.sort(key=lambda x: x.score, reverse=True)
            
            return scored_events
            
        except Exception as e:
            logger.error(f"OpenAI event matching failed: {e}")
            # Return basic scoring as fallback
            return [
                ScoredEvent(
                    event_id=str(event.get("_id", event.get("id", ""))),  # Handle both _id and id
                    score=50.0,
                    reasoning="Event available in Dubai",
                    highlights=["Local activity"]
                ) for event in events[:10]  # Limit fallback events too
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
Query analysis: {analysis.model_dump()}

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

IMPORTANT: You must respond with ONLY a valid JSON array of strings. Do not include any explanation, markdown formatting, or additional text.

Suggestions should:
- Be related but explore different angles
- Include timing variations if relevant
- Suggest price alternatives
- Offer category expansions
- Be actionable search phrases

Return format: ["suggestion 1", "suggestion 2", "suggestion 3", "suggestion 4"]"""

            user_prompt = f"""
Original query: "{query}"
Analysis: {analysis.model_dump()}
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
            
            raw_content = response.choices[0].message.content
            logger.debug(f"OpenAI suggestions raw response: {raw_content}")
            
            suggestions = self._extract_json_from_response(raw_content)
            if isinstance(suggestions, dict) and 'suggestions' in suggestions:
                suggestions = suggestions['suggestions']
            elif not isinstance(suggestions, list):
                logger.warning(f"Expected list of suggestions, got {type(suggestions)}")
                return ["Indoor activities", "Family events", "Weekend activities", "Free events"]
            
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