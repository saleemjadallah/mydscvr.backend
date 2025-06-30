"""
Event deduplication utilities for DXB Events API
Phase 4: Data Integration implementation
"""

import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from difflib import SequenceMatcher
import hashlib


class EventDeduplicator:
    """
    Smart event deduplication system using multiple matching strategies
    """
    
    def __init__(self, mongodb: AsyncIOMotorDatabase):
        self.mongodb = mongodb
        
        # Thresholds for duplicate detection
        self.title_similarity_threshold = 0.85
        self.venue_similarity_threshold = 0.8
        self.time_window_hours = 24  # Events within 24 hours are potential duplicates (increased from 6)
        self.description_similarity_threshold = 0.7
        
        # Common words to exclude from title comparison
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'among', 'within',
            'event', 'show', 'experience', 'festival', 'concert', 'exhibition'
        }
    
    async def is_duplicate_event(self, new_event: Dict[str, Any]) -> bool:
        """
        Check if the new event is a duplicate of an existing event
        """
        try:
            # Get potential duplicates using multiple strategies
            candidates = await self._get_duplicate_candidates(new_event)
            
            if not candidates:
                return False
            
            # Evaluate each candidate
            for candidate in candidates:
                # Use simple title-based similarity for more accurate duplicate detection
                title_similarity = self._calculate_text_similarity(
                    new_event.get("title", ""),
                    candidate.get("title", "")
                )
                
                # If titles are 85%+ similar, it's a duplicate - merge data instead of rejecting
                if title_similarity >= 0.85:
                    await self._handle_duplicate_found_with_merge(new_event, candidate, title_similarity)
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error in duplicate detection: {e}")
            return False  # If detection fails, allow the event to proceed
    
    async def _get_duplicate_candidates(self, new_event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get potential duplicate candidates using multiple search strategies
        """
        candidates = []
        
        # Strategy 1: Title-based search
        title_candidates = await self._search_by_title(new_event)
        candidates.extend(title_candidates)
        
        # Strategy 2: Venue and time-based search
        venue_time_candidates = await self._search_by_venue_and_time(new_event)
        candidates.extend(venue_time_candidates)
        
        # Strategy 3: Source ID matching (exact duplicates from same source)
        source_candidates = await self._search_by_source_id(new_event)
        candidates.extend(source_candidates)
        
        # Remove duplicates from candidates list
        unique_candidates = []
        seen_ids = set()
        
        for candidate in candidates:
            candidate_id = candidate.get("_id")
            if candidate_id not in seen_ids:
                unique_candidates.append(candidate)
                seen_ids.add(candidate_id)
        
        return unique_candidates
    
    async def _search_by_title(self, new_event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Search for events with similar titles - FIXED to avoid MongoDB query errors
        """
        title = new_event.get("title", "").strip()
        if not title:
            return []
        
        # Extract key words from title
        key_words = self._extract_key_words(title)
        
        if not key_words:
            return []
        
        # Use separate queries to avoid text search with $or errors
        candidates = []
        
        try:
            # Query 1: Direct title regex search (most reliable)
            title_query = {
                "title": {"$regex": re.escape(title[:30]), "$options": "i"}
            }
            title_candidates = await self.mongodb.events.find(title_query).limit(10).to_list(length=None)
            candidates.extend(title_candidates)
            
            # Query 2: Key words regex search for broader matching  
            if len(key_words) >= 2:
                keyword_pattern = "|".join([re.escape(word) for word in key_words[:3] if len(word) > 3])
                if keyword_pattern:
                    keyword_query = {
                        "title": {"$regex": keyword_pattern, "$options": "i"}
                    }
                    keyword_candidates = await self.mongodb.events.find(keyword_query).limit(10).to_list(length=None)
                    candidates.extend(keyword_candidates)
            
            # Query 3: Text search only (separate from other conditions)
            try:
                text_query = {"$text": {"$search": " ".join(key_words[:5])}}
                text_candidates = await self.mongodb.events.find(text_query).limit(5).to_list(length=None)
                candidates.extend(text_candidates)
            except Exception as text_error:
                # If text search fails, continue without it
                print(f"Text search failed (non-critical): {text_error}")
            
            # Remove duplicate candidates
            unique_candidates = []
            seen_ids = set()
            for candidate in candidates:
                candidate_id = str(candidate.get("_id"))
                if candidate_id not in seen_ids:
                    unique_candidates.append(candidate)
                    seen_ids.add(candidate_id)
            
            return unique_candidates
            
        except Exception as e:
            print(f"Error in title search: {e}")
            # Fallback to simple title regex only
            try:
                fallback_query = {
                    "title": {"$regex": re.escape(title[:20]), "$options": "i"}
                }
                return await self.mongodb.events.find(fallback_query).limit(5).to_list(length=None)
            except Exception as fallback_error:
                print(f"Even fallback search failed: {fallback_error}")
                return []
    
    async def _search_by_venue_and_time(self, new_event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Search for events at the same venue around the same time
        """
        venue_name = new_event.get("venue_name", "").strip()
        start_date = new_event.get("start_date")
        
        if not venue_name or not start_date:
            return []
        
        # Create time window
        if isinstance(start_date, str):
            try:
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return []
        
        time_before = start_date - timedelta(hours=self.time_window_hours)
        time_after = start_date + timedelta(hours=self.time_window_hours)
        
        # Search for events at similar venue and time
        search_query = {
            "$and": [
                {
                    "$or": [
                        {"venue_name": {"$regex": re.escape(venue_name[:15]), "$options": "i"}},
                        {"venue_address": {"$regex": re.escape(venue_name[:15]), "$options": "i"}}
                    ]
                },
                {
                    "start_date": {
                        "$gte": time_before,
                        "$lte": time_after
                    }
                }
            ]
        }
        
        candidates = await self.mongodb.events.find(search_query).limit(10).to_list(length=None)
        return candidates
    
    async def _search_by_source_id(self, new_event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Search for events with the same source ID (exact duplicates)
        """
        source_id = new_event.get("source_id")
        source_name = new_event.get("source_name")
        
        if not source_id:
            return []
        
        search_query = {
            "source_id": source_id,
            "source_name": source_name
        }
        
        candidates = await self.mongodb.events.find(search_query).limit(5).to_list(length=None)
        return candidates
    
    def _normalize_title_for_grouping(self, title: str) -> str:
        """
        Normalize title for grouping - handles UTF-8 properly
        """
        if not title:
            return ""
        
        # Convert to lowercase and remove punctuation
        normalized = re.sub(r'[^\w\s]', ' ', title.lower())
        # Replace multiple spaces with single space
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Take first 3-4 meaningful words for grouping
        words = [w for w in normalized.split() if w not in self.stop_words and len(w) > 2]
        key_words = words[:4] if words else [normalized[:15]]
        
        return ' '.join(key_words)
    
    def _extract_key_words(self, text: str) -> List[str]:
        """
        Extract meaningful keywords from text for comparison
        """
        if not text:
            return []
        
        # Clean and normalize text
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = text.split()
        
        # Filter out stop words and short words
        key_words = [
            word for word in words
            if len(word) > 2 and word not in self.stop_words
        ]
        
        return key_words[:10]  # Limit to top 10 keywords
    
    def _calculate_similarity_score(self, event1: Dict[str, Any], event2: Dict[str, Any]) -> float:
        """
        Calculate overall similarity score between two events
        """
        scores = {}
        
        # Title similarity (weight: 50% - increased from 40%)
        title_score = self._calculate_text_similarity(
            event1.get("title", ""),
            event2.get("title", "")
        )
        scores["title"] = title_score * 0.5
        
        # If titles are very similar, apply bonus multiplier
        if title_score > 0.9:
            scores["title"] = min(1.0, scores["title"] * 1.2)
        
        # Venue similarity (weight: 20% - reduced from 25%)
        venue_score = self._calculate_text_similarity(
            event1.get("venue_name", ""),
            event2.get("venue_name", "")
        )
        scores["venue"] = venue_score * 0.20
        
        # Time similarity (weight: 15% - reduced from 20%)
        time_score = self._calculate_time_similarity(
            event1.get("start_date"),
            event2.get("start_date")
        )
        scores["time"] = time_score * 0.15
        
        # Description similarity (weight: 10%)
        desc_score = self._calculate_text_similarity(
            event1.get("description", ""),
            event2.get("description", "")
        )
        scores["description"] = desc_score * 0.1
        
        # Source exact match (weight: 5%)
        source_score = 1.0 if (
            event1.get("source_id") == event2.get("source_id") and
            event1.get("source_name") == event2.get("source_name")
        ) else 0.0
        scores["source"] = source_score * 0.05
        
        # Calculate weighted total
        total_score = sum(scores.values())
        
        return min(1.0, total_score)
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two text strings
        """
        if not text1 or not text2:
            return 0.0
        
        # Normalize texts
        text1 = re.sub(r'[^\w\s]', ' ', text1.lower()).strip()
        text2 = re.sub(r'[^\w\s]', ' ', text2.lower()).strip()
        
        if not text1 or not text2:
            return 0.0
        
        # Use sequence matcher for basic similarity
        basic_similarity = SequenceMatcher(None, text1, text2).ratio()
        
        # Use word-based similarity for additional check
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return basic_similarity
        
        # Calculate Jaccard similarity (intersection over union)
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        word_similarity = intersection / union if union > 0 else 0.0
        
        # Return weighted average
        return (basic_similarity * 0.6) + (word_similarity * 0.4)
    
    def _calculate_time_similarity(self, time1: Any, time2: Any) -> float:
        """
        Calculate similarity between two timestamps
        """
        if not time1 or not time2:
            return 0.0
        
        # Convert to datetime objects if needed
        if isinstance(time1, str):
            try:
                time1 = datetime.fromisoformat(time1.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return 0.0
        
        if isinstance(time2, str):
            try:
                time2 = datetime.fromisoformat(time2.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return 0.0
        
        if not isinstance(time1, datetime) or not isinstance(time2, datetime):
            return 0.0
        
        # Calculate time difference in hours
        time_diff = abs((time1 - time2).total_seconds()) / 3600
        
        # Create similarity score based on time difference
        if time_diff <= 1:  # Within 1 hour
            return 1.0
        elif time_diff <= 6:  # Within 6 hours
            return 1.0 - (time_diff - 1) / 5 * 0.5  # Linear decrease
        elif time_diff <= 24:  # Within 24 hours
            return 0.5 - (time_diff - 6) / 18 * 0.4  # Further decrease
        else:  # More than 24 hours
            return 0.1
    
    async def _handle_duplicate_found(
        self, 
        new_event: Dict[str, Any], 
        existing_event: Dict[str, Any], 
        similarity_score: float
    ):
        """
        Handle actions when a duplicate is found
        """
        try:
            # Log the duplicate detection
            duplicate_log = {
                "new_event": {
                    "source_id": new_event.get("source_id"),
                    "source_name": new_event.get("source_name"),
                    "title": new_event.get("title")
                },
                "existing_event": {
                    "_id": existing_event.get("_id"),
                    "title": existing_event.get("title"),
                    "source_name": existing_event.get("source_name")
                },
                "similarity_score": similarity_score,
                "detected_at": datetime.now(timezone.utc),
                "action": "rejected_duplicate"
            }
            
            # Store duplicate detection log
            await self.mongodb.duplicate_logs.insert_one(duplicate_log)
            
            # Update existing event with additional source information if beneficial
            await self._merge_event_data(new_event, existing_event)
            
        except Exception as e:
            print(f"Error handling duplicate: {e}")
    
    async def _merge_event_data(self, new_event: Dict[str, Any], existing_event: Dict[str, Any]):
        """
        Merge useful data from new event into existing event
        """
        try:
            update_fields = {}
            
            # Merge image URLs
            existing_images = existing_event.get("image_urls", [])
            new_images = new_event.get("image_urls", [])
            all_images = list(set(existing_images + new_images))
            if len(all_images) > len(existing_images):
                update_fields["image_urls"] = all_images
            
            # Update booking URL if missing
            if not existing_event.get("booking_url") and new_event.get("booking_url"):
                update_fields["booking_url"] = new_event.get("booking_url")
            
            # Merge tags
            existing_tags = existing_event.get("tags", [])
            new_tags = new_event.get("tags", [])
            all_tags = list(set(existing_tags + new_tags))
            if len(all_tags) > len(existing_tags):
                update_fields["tags"] = all_tags
            
            # Add source tracking
            if "source_tracking" not in existing_event:
                update_fields["source_tracking"] = []
            
            source_info = {
                "source_name": new_event.get("source_name"),
                "source_id": new_event.get("source_id"),
                "first_seen": datetime.now(timezone.utc),
                "data": new_event.get("source_data", {})
            }
            
            update_fields["$push"] = {"source_tracking": source_info}
            update_fields["last_updated"] = datetime.now(timezone.utc)
            
            # Perform update if there are changes
            if update_fields:
                await self.mongodb.events.update_one(
                    {"_id": existing_event["_id"]},
                    {"$set": {k: v for k, v in update_fields.items() if k != "$push"},
                     "$push": update_fields.get("$push", {})}
                )
            
        except Exception as e:
            print(f"Error merging event data: {e}")
    
    async def _handle_duplicate_found_with_merge(
        self, 
        new_event: Dict[str, Any], 
        existing_event: Dict[str, Any], 
        title_similarity: float
    ):
        """
        Handle duplicates with improved merging strategy - focus on title similarity
        """
        try:
            # Log the duplicate detection with new approach
            duplicate_log = {
                "new_event": {
                    "source_id": new_event.get("source_id"),
                    "source_name": new_event.get("source_name", new_event.get("source", "unknown")),
                    "title": new_event.get("title")
                },
                "existing_event": {
                    "_id": existing_event.get("_id"),
                    "title": existing_event.get("title"),
                    "source_name": existing_event.get("source_name", existing_event.get("source", "unknown"))
                },
                "title_similarity": title_similarity,
                "detected_at": datetime.now(timezone.utc),
                "action": "merged_duplicate",
                "method": "title_based_90_percent"
            }
            
            # Store duplicate detection log
            await self.mongodb.duplicate_logs.insert_one(duplicate_log)
            
            # Enhanced merge: prioritize more complete data
            await self._enhanced_merge_event_data(new_event, existing_event)
            
        except Exception as e:
            print(f"Error handling duplicate with merge: {e}")
    
    async def _enhanced_merge_event_data(self, new_event: Dict[str, Any], existing_event: Dict[str, Any]):
        """
        Enhanced merge: prioritize more complete data and create comprehensive events
        """
        try:
            update_fields = {}
            
            # Smart title merging - prefer more descriptive titles
            existing_title = existing_event.get("title", "")
            new_title = new_event.get("title", "")
            
            if len(new_title) > len(existing_title) and "VIP" not in new_title:
                update_fields["title"] = new_title
            elif "Premier" in new_title or "Dubai's" in new_title:
                update_fields["title"] = new_title
            
            # Intelligent pricing merge - create comprehensive price ranges
            existing_pricing = existing_event.get("pricing", {})
            new_pricing = new_event.get("pricing", {})
            
            if existing_pricing and new_pricing:
                # Calculate comprehensive price range
                min_price = min(
                    existing_pricing.get("base_price", float('inf')),
                    new_pricing.get("base_price", float('inf'))
                )
                max_price = max(
                    existing_pricing.get("max_price", 0),
                    new_pricing.get("max_price", 0),
                    existing_pricing.get("base_price", 0),
                    new_pricing.get("base_price", 0)
                )
                
                # Create intelligent pricing tiers
                pricing_notes = self._generate_pricing_tiers(min_price, max_price)
                
                comprehensive_pricing = {
                    "base_price": min_price,
                    "max_price": max_price,
                    "currency": existing_pricing.get("currency", "AED"),
                    "is_refundable": existing_pricing.get("is_refundable", True),
                    "pricing_notes": pricing_notes
                }
                update_fields["pricing"] = comprehensive_pricing
            
            # Merge showtimes if different
            existing_start = existing_event.get("start_date")
            new_start = new_event.get("start_date")
            
            if existing_start and new_start:
                existing_showtimes = existing_event.get("showtimes", [])
                if not existing_showtimes:
                    # Convert existing start_date to showtime format
                    if isinstance(existing_start, str):
                        existing_start = datetime.fromisoformat(existing_start.replace('Z', '+00:00'))
                    existing_showtimes = [existing_start.strftime("%H:%M")]
                
                # Add new showtime if different
                if isinstance(new_start, str):
                    new_start = datetime.fromisoformat(new_start.replace('Z', '+00:00'))
                new_showtime = new_start.strftime("%H:%M")
                
                if new_showtime not in existing_showtimes:
                    existing_showtimes.append(new_showtime)
                    existing_showtimes.sort()
                    update_fields["showtimes"] = existing_showtimes
                    
                    # Update description to mention multiple showtimes
                    existing_desc = existing_event.get("description", "")
                    if "Multiple showtimes" not in existing_desc:
                        update_fields["description"] = existing_desc + " Multiple showtimes available throughout the day."
            
            # Enhanced description merging
            existing_desc = existing_event.get("description", "")
            new_desc = new_event.get("description", "")
            
            if len(new_desc) > len(existing_desc) and new_desc != existing_desc:
                # Keep the more comprehensive description
                update_fields["description"] = new_desc
            elif existing_desc and "spectacular" not in existing_desc and "spectacular" in new_desc:
                update_fields["description"] = new_desc
            
            # Merge image URLs intelligently
            existing_images = existing_event.get("image_urls", [])
            new_images = new_event.get("image_urls", [])
            all_images = list(set(existing_images + new_images))
            if len(all_images) > len(existing_images):
                update_fields["image_urls"] = all_images
            
            # Track multiple sources intelligently
            existing_sources = existing_event.get("sources", [])
            if not existing_sources:
                existing_sources = [existing_event.get("source", "unknown")]
            
            new_source = new_event.get("source", "unknown")
            if new_source not in existing_sources:
                existing_sources.append(new_source)
                update_fields["sources"] = existing_sources
            
            # Add merge tracking for transparency
            existing_merged_from = existing_event.get("merged_from", [])
            new_title_for_tracking = new_event.get("title", "Unknown Event")
            if new_title_for_tracking not in existing_merged_from:
                existing_merged_from.append(new_title_for_tracking)
                update_fields["merged_from"] = existing_merged_from
            
            # Enhanced extraction metadata
            existing_metadata = existing_event.get("extraction_metadata", {})
            new_metadata = new_event.get("extraction_metadata", {})
            
            merged_metadata = existing_metadata.copy()
            merged_metadata.update({
                "merged_from_sources": existing_sources,
                "last_merge_timestamp": datetime.now(timezone.utc).isoformat(),
                "merge_method": "intelligent_comprehensive_merge",
                "pricing_intelligently_merged": bool(update_fields.get("pricing")),
                "showtimes_merged": bool(update_fields.get("showtimes"))
            })
            
            # Add new metadata that doesn't overwrite existing
            for key, value in new_metadata.items():
                if key not in merged_metadata and value:
                    merged_metadata[key] = value
            
            update_fields["extraction_metadata"] = merged_metadata
            update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # Apply updates if we have any
            if update_fields:
                await self.mongodb.events.update_one(
                    {"_id": existing_event["_id"]},
                    {"$set": update_fields}
                )
                print(f"🧠 Intelligent merge completed for: {existing_event.get('title', 'Unknown title')}")
                print(f"   📊 Price range: {update_fields.get('pricing', {}).get('base_price', 'N/A')}-{update_fields.get('pricing', {}).get('max_price', 'N/A')} AED")
                if update_fields.get("showtimes"):
                    print(f"   🕐 Showtimes: {', '.join(update_fields['showtimes'])}")
            
        except Exception as e:
            print(f"Error in intelligent merge: {e}")
    
    def _generate_pricing_tiers(self, min_price: float, max_price: float) -> str:
        """
        Generate intelligent pricing tier descriptions based on price range
        """
        if max_price <= min_price * 1.2:
            return f"Single tier pricing (AED {int(min_price)})"
        
        # Calculate tier ranges
        range_size = max_price - min_price
        tier1_max = min_price + (range_size * 0.4)
        tier2_max = min_price + (range_size * 0.7)
        
        return f"Multiple pricing tiers available - Standard (AED {int(min_price)}-{int(tier1_max)}), Premium (AED {int(tier1_max+1)}-{int(tier2_max)}), VIP (AED {int(tier2_max+1)}-{int(max_price)})"
    
    async def get_duplicate_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about duplicate detection
        """
        try:
            # Get duplicate detection logs
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            week_ago = today - timedelta(days=7)
            
            # Get total events count
            total_events = await self.mongodb.events.count_documents({})
            
            # Today's duplicates
            today_duplicates = await self.mongodb.duplicate_logs.count_documents({
                "detected_at": {"$gte": today}
            })
            
            # Week's duplicates
            week_duplicates = await self.mongodb.duplicate_logs.count_documents({
                "detected_at": {"$gte": week_ago}
            })
            
            # Total duplicates
            total_duplicates = await self.mongodb.duplicate_logs.count_documents({})
            
            # Find estimated duplicates using title similarity
            estimated_duplicates = await self._count_potential_duplicates()
            
            # Top duplicate sources
            pipeline = [
                {"$group": {
                    "_id": "$new_event.source_name",
                    "duplicate_count": {"$sum": 1}
                }},
                {"$sort": {"duplicate_count": -1}},
                {"$limit": 5}
            ]
            
            top_sources = await self.mongodb.duplicate_logs.aggregate(pipeline).to_list(length=None)
            
            return {
                "total_events": total_events,
                "today_duplicates": today_duplicates,
                "week_duplicates": week_duplicates,
                "total_duplicates": total_duplicates,
                "estimated_duplicates": estimated_duplicates,
                "top_duplicate_sources": top_sources,
                "deduplication_rate": f"{(total_duplicates / max(1, total_duplicates + total_events) * 100):.1f}%"
            }
            
        except Exception as e:
            print(f"Error getting duplicate statistics: {e}")
            return {
                "total_events": 0,
                "today_duplicates": 0,
                "week_duplicates": 0,
                "total_duplicates": 0,
                "estimated_duplicates": 0,
                "top_duplicate_sources": [],
                "deduplication_rate": "0.0%"
            }

    async def _count_potential_duplicates(self) -> int:
        """
        Count potential duplicates using title similarity
        """
        try:
            # Find events with similar titles using aggregation
            pipeline = [
                {"$group": {
                    "_id": "$title",
                    "count": {"$sum": 1}
                }},
                {"$match": {"count": {"$gt": 1}}},
                {"$group": {
                    "_id": None,
                    "total_duplicates": {"$sum": {"$subtract": ["$count", 1]}}
                }}
            ]
            
            result = await self.mongodb.events.aggregate(pipeline).to_list(length=None)
            if result:
                return result[0].get("total_duplicates", 0)
            return 0
            
        except Exception as e:
            print(f"Error counting potential duplicates: {e}")
            return 0
    
    async def find_potential_duplicates(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Find potential duplicates using Python-based grouping instead of MongoDB $substr
        This avoids UTF-8 character issues with $substr
        """
        try:
            print("🔍 Fetching all event titles and IDs...")
            
            # First, get all events with basic info - avoid aggregation with $substr
            all_events = await self.mongodb.events.find(
                {},
                {"title": 1, "venue.name": 1, "start_date": 1, "created_at": 1}
            ).to_list(length=None)
            
            print(f"📊 Analyzing {len(all_events)} events for duplicates...")
            
            # Group events by normalized title using Python (not MongoDB)
            title_groups = {}
            for event in all_events:
                title = event.get("title", "")
                normalized_title = self._normalize_title_for_grouping(title)
                
                if normalized_title not in title_groups:
                    title_groups[normalized_title] = []
                title_groups[normalized_title].append(event)
            
            # Find groups with multiple events
            potential_duplicates = []
            groups_with_duplicates = {k: v for k, v in title_groups.items() if len(v) > 1}
            
            print(f"🔍 Found {len(groups_with_duplicates)} groups with potential duplicates")
            
            for normalized_title, events in groups_with_duplicates.items():
                if len(events) < 2:
                    continue
                
                print(f"  📝 Analyzing group: '{normalized_title}' ({len(events)} events)")
                
                # Compare each pair in the group
                for i in range(len(events)):
                    for j in range(i + 1, len(events)):
                        event1 = events[i]
                        event2 = events[j]
                        
                        # Calculate detailed similarity
                        similarity = self._calculate_text_similarity(
                            event1.get("title", ""), 
                            event2.get("title", "")
                        )
                        
                        if similarity > 0.75:  # 75% threshold for investigation
                            # Choose which event to keep (older one typically has more stable data)
                            created1 = event1.get("created_at", datetime.min)
                            created2 = event2.get("created_at", datetime.min)
                            
                            if isinstance(created1, str):
                                try:
                                    created1 = datetime.fromisoformat(created1.replace('Z', '+00:00'))
                                except:
                                    created1 = datetime.min
                            if isinstance(created2, str):
                                try:
                                    created2 = datetime.fromisoformat(created2.replace('Z', '+00:00'))
                                except:
                                    created2 = datetime.min
                            
                            older_event = event1 if created1 < created2 else event2
                            newer_event = event2 if older_event == event1 else event1
                            
                            potential_duplicates.append({
                                "duplicate_id": newer_event["_id"],
                                "keep_id": older_event["_id"],
                                "similarity_score": similarity,
                                "duplicate_title": newer_event.get("title", "Unknown"),
                                "keep_title": older_event.get("title", "Unknown"),
                                "needs_review": similarity < 0.90,
                                "group_key": normalized_title
                            })
                            
                            # Limit pairs per group to avoid explosion
                            if len(potential_duplicates) >= limit * 2:
                                break
                    
                    if len(potential_duplicates) >= limit * 2:
                        break
                
                if len(potential_duplicates) >= limit * 2:
                    break
            
            # Sort by similarity score (highest first) and limit
            potential_duplicates.sort(key=lambda x: x["similarity_score"], reverse=True)
            return potential_duplicates[:limit]
            
        except Exception as e:
            print(f"Error finding potential duplicates: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def find_and_merge_similar_events(self, similarity_threshold: float = 0.8) -> Dict[str, Any]:
        """
        Proactively find and merge similar events that weren't caught during collection
        Returns statistics about the merging process
        """
        try:
            merge_stats = {
                "events_analyzed": 0,
                "groups_found": 0,
                "events_merged": 0,
                "events_removed": 0,
                "comprehensive_events_created": 0
            }
            
            # Get future events and group them in Python to avoid UTF-8 issues with $substr
            future_events = await self.mongodb.events.find(
                {"start_date": {"$gte": datetime.now(timezone.utc)}},
                {"title": 1, "venue.name": 1, "start_date": 1, "created_at": 1}
            ).limit(1000).to_list(length=None)  # Limit for performance
            
            # Group events by normalized title + venue + date using Python
            merge_groups = {}
            for event in future_events:
                # Create grouping key
                title_prefix = self._normalize_title_for_grouping(event.get("title", ""))
                venue = event.get("venue", {}).get("name", "unknown")
                try:
                    start_date = event.get("start_date")
                    if isinstance(start_date, str):
                        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    date_str = start_date.strftime("%Y-%m-%d") if start_date else "unknown"
                except:
                    date_str = "unknown"
                
                group_key = f"{title_prefix}|{venue}|{date_str}"
                
                if group_key not in merge_groups:
                    merge_groups[group_key] = []
                merge_groups[group_key].append(event)
            
            # Convert to potential_groups format for compatibility
            potential_groups = []
            for group_key, events in merge_groups.items():
                if len(events) > 1:
                    potential_groups.append({
                        "events": events,
                        "count": len(events)
                    })
                    if len(potential_groups) >= 20:  # Limit processing
                        break
            merge_stats["groups_found"] = len(potential_groups)
            
            for group in potential_groups:
                events = group.get("events", [])
                merge_stats["events_analyzed"] += len(events)
                
                if len(events) < 2:
                    continue
                
                # Find the best "master" event (most comprehensive)
                master_event = self._select_master_event(events)
                remaining_events = [e for e in events if e["_id"] != master_event["_id"]]
                
                # Check if events are truly similar
                merge_candidates = []
                for event in remaining_events:
                    similarity = self._calculate_text_similarity(
                        master_event.get("title", ""),
                        event.get("title", "")
                    )
                    
                    if similarity >= similarity_threshold:
                        merge_candidates.append(event)
                
                if merge_candidates:
                    # Perform intelligent merge
                    await self._merge_multiple_events(master_event, merge_candidates)
                    merge_stats["events_merged"] += len(merge_candidates)
                    merge_stats["events_removed"] += len(merge_candidates)
                    merge_stats["comprehensive_events_created"] += 1
            
            return merge_stats
            
        except Exception as e:
            print(f"Error in proactive similar event merging: {e}")
            return merge_stats
    
    def _select_master_event(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Select the best master event for merging based on data completeness
        """
        def score_event(event):
            score = 0
            # Prefer events with price ranges
            pricing = event.get("pricing", {})
            if pricing.get("max_price", 0) > pricing.get("base_price", 0):
                score += 3
            
            # Prefer longer descriptions  
            desc_len = len(event.get("description", ""))
            score += min(desc_len / 100, 2)  # Max 2 points
            
            # Prefer events with images
            if event.get("image_urls"):
                score += 1
                
            # Prefer more recent events
            created = event.get("created_at")
            if created and isinstance(created, datetime):
                days_old = (datetime.now(timezone.utc) - created).days
                score += max(0, 1 - days_old / 30)  # Newer is better
            
            # Prefer more descriptive titles
            title_len = len(event.get("title", ""))
            score += min(title_len / 50, 1)  # Max 1 point
            
            return score
        
        return max(events, key=score_event)
    
    async def _merge_multiple_events(self, master_event: Dict[str, Any], merge_candidates: List[Dict[str, Any]]):
        """
        Merge multiple events into one comprehensive master event
        """
        try:
            update_fields = {}
            
            # Collect all pricing information
            all_prices = [master_event.get("pricing", {})]
            all_showtimes = []
            all_sources = [master_event.get("source", "unknown")]
            all_titles = [master_event.get("title", "")]
            all_images = master_event.get("image_urls", [])
            
            # Extract master showtime
            master_start = master_event.get("start_date")
            if master_start:
                if isinstance(master_start, str):
                    master_start = datetime.fromisoformat(master_start.replace('Z', '+00:00'))
                all_showtimes.append(master_start.strftime("%H:%M"))
            
            # Collect data from all candidates
            for candidate in merge_candidates:
                # Collect pricing
                candidate_pricing = candidate.get("pricing", {})
                if candidate_pricing:
                    all_prices.append(candidate_pricing)
                
                # Collect showtimes
                candidate_start = candidate.get("start_date")
                if candidate_start:
                    if isinstance(candidate_start, str):
                        candidate_start = datetime.fromisoformat(candidate_start.replace('Z', '+00:00'))
                    showtime = candidate_start.strftime("%H:%M")
                    if showtime not in all_showtimes:
                        all_showtimes.append(showtime)
                
                # Collect sources
                candidate_source = candidate.get("source", "unknown")
                if candidate_source not in all_sources:
                    all_sources.append(candidate_source)
                
                # Collect titles for tracking
                candidate_title = candidate.get("title", "")
                if candidate_title and candidate_title not in all_titles:
                    all_titles.append(candidate_title)
                
                # Collect images
                candidate_images = candidate.get("image_urls", [])
                all_images.extend([img for img in candidate_images if img not in all_images])
            
            # Create comprehensive pricing
            if len(all_prices) > 1:
                valid_prices = [p for p in all_prices if p.get("base_price")]
                if valid_prices:
                    min_price = min(p.get("base_price", float('inf')) for p in valid_prices)
                    max_price = max(
                        max(p.get("max_price", 0), p.get("base_price", 0)) 
                        for p in valid_prices
                    )
                    
                    pricing_notes = self._generate_pricing_tiers(min_price, max_price)
                    
                    update_fields["pricing"] = {
                        "base_price": min_price,
                        "max_price": max_price,
                        "currency": valid_prices[0].get("currency", "AED"),
                        "is_refundable": True,
                        "pricing_notes": pricing_notes
                    }
            
            # Set showtimes if multiple
            if len(all_showtimes) > 1:
                all_showtimes.sort()
                update_fields["showtimes"] = all_showtimes
                
                # Update description
                existing_desc = master_event.get("description", "")
                if "Multiple showtimes" not in existing_desc:
                    update_fields["description"] = existing_desc + " Multiple showtimes available throughout the day."
            
            # Set comprehensive metadata
            update_fields.update({
                "sources": all_sources,
                "merged_from": all_titles[1:],  # Exclude master title
                "image_urls": all_images,
                "extraction_metadata": {
                    **master_event.get("extraction_metadata", {}),
                    "proactively_merged": True,
                    "merge_timestamp": datetime.now(timezone.utc).isoformat(),
                    "merge_method": "proactive_intelligent_merge",
                    "events_merged_count": len(merge_candidates)
                },
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Update master event
            if update_fields:
                await self.mongodb.events.update_one(
                    {"_id": master_event["_id"]},
                    {"$set": update_fields}
                )
                
                print(f"🚀 Proactively merged {len(merge_candidates)} events into: {master_event.get('title', 'Unknown')}")
                if update_fields.get("pricing"):
                    pricing = update_fields["pricing"]
                    print(f"   💰 Price range: AED {pricing['base_price']}-{pricing['max_price']}")
                if update_fields.get("showtimes"):
                    print(f"   🕐 Showtimes: {', '.join(update_fields['showtimes'])}")
            
            # Remove merged events
            candidate_ids = [candidate["_id"] for candidate in merge_candidates]
            await self.mongodb.events.delete_many({"_id": {"$in": candidate_ids}})
            
        except Exception as e:
            print(f"Error merging multiple events: {e}") 