# AI Search Configuration for MongoDB Events - Complete Implementation

## OpenAI API Configuration

```javascript
const configuration = {
  model: "gpt-4o-mini", // Cost-effective, fast, good for search tasks
  temperature: 0.3,     // Lower temperature for more consistent results
  max_tokens: 1500,     // Increased for complex queries
  top_p: 0.9,          // Slightly focused responses
  frequency_penalty: 0.0,
  presence_penalty: 0.0
}
```

## System Prompt

```
You are an intelligent search assistant for a Dubai events database. Your role is to analyze user search queries and match them with relevant events from the provided MongoDB collection data.

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
- venue.coordinates: GPS location {lat, lng}
- familyScore: Family suitability score (0-100)
- is_family_friendly: Boolean flag
- age_min/age_max/age_group/age_restrictions: Age-related fields
- tags: Array of keywords
- status: Event status (active, cancelled, postponed)

TEMPORAL SEARCH UNDERSTANDING:
Today's date is: [CURRENT_DATE]

When users search with temporal keywords, interpret them as follows:
- "today" = events where start_date is on [CURRENT_DATE]
- "tomorrow" = events where start_date is on [CURRENT_DATE + 1 day]
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
```

## User Prompt Template

```
Search Query: [USER_KEYWORDS]
Current Date: [CURRENT_DATE_ISO]
Current Day of Week: [CURRENT_DAY_NAME]
Current Time: [CURRENT_TIME]

Database Events:
[MONGODB_EVENTS_JSON]

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

Remember: Only reference events that exist in the provided database data.
```

## Implementation Example

```javascript
const { DateTime } = require('luxon');

async function searchEvents(userKeywords, mongodbEvents) {
  const openai = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY
  });

  // Get current date/time info for Dubai timezone
  const dubaiTime = DateTime.now().setZone('Asia/Dubai');
  const currentDate = dubaiTime.toISODate();
  const currentDayName = dubaiTime.toFormat('cccc');
  const currentTime = dubaiTime.toFormat('HH:mm');

  // Convert MongoDB events to JSON string with formatted dates
  const formattedEvents = mongodbEvents.map(event => ({
    ...event.toObject(),
    // Ensure consistent date formatting
    start_date: event.start_date?.toISOString(),
    end_date: event.end_date?.toISOString(),
    // Add computed fields for easier matching
    dayOfWeek: event.start_date ? DateTime.fromJSDate(event.start_date).toFormat('cccc') : null,
    startTime: event.start_date ? DateTime.fromJSDate(event.start_date).toFormat('HH:mm') : null
  }));

  const eventsJson = JSON.stringify(formattedEvents, null, 2);

  const completion = await openai.chat.completions.create({
    model: "gpt-4o-mini",
    temperature: 0.3,
    max_tokens: 1500,
    messages: [
      {
        role: "system",
        content: SYSTEM_PROMPT // Full system prompt from above
      },
      {
        role: "user",
        content: `Search Query: ${userKeywords}
Current Date: ${currentDate}
Current Day of Week: ${currentDayName}
Current Time: ${currentTime}

Database Events:
${eventsJson}

Please analyze the search query...` // Full user prompt from above
      }
    ]
  });

  return completion.choices[0].message.content;
}
```

## Advanced Query Helpers

```javascript
// Comprehensive keyword extraction
function extractSearchCriteria(keywords) {
  const criteria = {
    temporal: extractTemporalCriteria(keywords),
    price: extractPriceCriteria(keywords),
    location: extractLocationCriteria(keywords),
    category: extractCategoryCriteria(keywords),
    family: extractFamilyCriteria(keywords),
    venue: extractVenueCriteria(keywords)
  };
  
  return criteria;
}

// Extract temporal criteria with Dubai timezone
function extractTemporalCriteria(keywords) {
  const { DateTime } = require('luxon');
  const now = DateTime.now().setZone('Asia/Dubai');
  const keywordsLower = keywords.toLowerCase();
  
  let startDate, endDate, timeOfDay;
  
  // Date extraction
  if (keywordsLower.includes('today')) {
    startDate = now.startOf('day');
    endDate = now.endOf('day');
  } else if (keywordsLower.includes('tomorrow')) {
    startDate = now.plus({ days: 1 }).startOf('day');
    endDate = now.plus({ days: 1 }).endOf('day');
  } else if (keywordsLower.includes('this weekend') || keywordsLower.includes('weekend')) {
    const daysUntilSaturday = (6 - now.weekday + 7) % 7 || 7;
    startDate = now.plus({ days: daysUntilSaturday }).startOf('day');
    endDate = startDate.plus({ days: 1 }).endOf('day');
  }
  
  // Time of day extraction
  if (keywordsLower.includes('tonight')) {
    timeOfDay = { start: 18, end: 23 };
  } else if (keywordsLower.includes('morning')) {
    timeOfDay = { start: 6, end: 12 };
  } else if (keywordsLower.includes('afternoon')) {
    timeOfDay = { start: 12, end: 18 };
  }
  
  return { startDate, endDate, timeOfDay };
}

// Extract price criteria with multiple field support
function extractPriceCriteria(keywords) {
  const keywordsLower = keywords.toLowerCase();
  
  if (keywordsLower.includes('free')) {
    return { type: 'free', min: 0, max: 0 };
  } else if (keywordsLower.match(/cheap|budget|affordable/)) {
    return { type: 'budget', min: 0, max: 50 };
  } else if (keywordsLower.match(/expensive|premium|luxury/)) {
    return { type: 'premium', min: 200, max: null };
  }
  
  // Extract specific price mentions
  const priceMatch = keywordsLower.match(/(?:under|less than|below)\s+(\d+)/);
  if (priceMatch) {
    return { type: 'under', min: 0, max: parseInt(priceMatch[1]) };
  }
  
  const aroundMatch = keywordsLower.match(/around\s+(\d+)/);
  if (aroundMatch) {
    const target = parseInt(aroundMatch[1]);
    return { type: 'around', min: target * 0.8, max: target * 1.2 };
  }
  
  return null;
}

// Extract Dubai location criteria
function extractLocationCriteria(keywords) {
  const locations = {
    'downtown': ['downtown', 'dubai mall', 'burj khalifa'],
    'marina': ['marina', 'marina walk', 'marina mall'],
    'jbr': ['jbr', 'jumeirah beach residence', 'the beach', 'the walk'],
    'business bay': ['business bay'],
    'difc': ['difc', 'financial centre'],
    'jumeirah': ['jumeirah', 'jumeirah beach'],
    'deira': ['deira', 'old dubai', 'gold souk']
  };
  
  const keywordsLower = keywords.toLowerCase();
  
  for (const [area, patterns] of Object.entries(locations)) {
    for (const pattern of patterns) {
      if (keywordsLower.includes(pattern)) {
        return area;
      }
    }
  }
  
  return null;
}
```

## MongoDB Query Builder

```javascript
// Build comprehensive MongoDB query from extracted criteria
async function buildMongoQuery(keywords) {
  const criteria = extractSearchCriteria(keywords);
  const query = { status: { $ne: 'cancelled' } }; // Exclude cancelled by default
  
  // Temporal filtering
  if (criteria.temporal?.startDate) {
    query.$and = query.$and || [];
    query.$and.push({
      $or: [
        { 
          start_date: { 
            $gte: criteria.temporal.startDate.toJSDate(),
            $lte: criteria.temporal.endDate.toJSDate()
          }
        },
        // Handle events spanning multiple days
        {
          $and: [
            { start_date: { $lte: criteria.temporal.endDate.toJSDate() } },
            { end_date: { $gte: criteria.temporal.startDate.toJSDate() } }
          ]
        }
      ]
    });
    
    // Time of day filtering
    if (criteria.temporal.timeOfDay) {
      query.$and.push({
        $expr: {
          $and: [
            { $gte: [{ $hour: "$start_date" }, criteria.temporal.timeOfDay.start] },
            { $lte: [{ $hour: "$start_date" }, criteria.temporal.timeOfDay.end] }
          ]
        }
      });
    }
  }
  
  // Price filtering with multiple field support
  if (criteria.price) {
    query.$and = query.$and || [];
    
    if (criteria.price.type === 'free') {
      query.$and.push({
        $or: [
          { price: { $regex: /free/i } },
          { 'pricing.base_price': 0 },
          { price: '0' },
          { price: 'Free' }
        ]
      });
    } else if (criteria.price.max !== null) {
      query.$and.push({
        $or: [
          { 'pricing.base_price': { $lte: criteria.price.max } },
          { 'price_data.min': { $lte: criteria.price.max } }
        ]
      });
    }
  }
  
  // Location filtering
  if (criteria.location) {
    query.$or = [
      { 'venue.area': { $regex: new RegExp(criteria.location, 'i') } },
      { location: { $regex: new RegExp(criteria.location, 'i') } },
      { address: { $regex: new RegExp(criteria.location, 'i') } }
    ];
  }
  
  // Family filtering
  if (criteria.family?.familyFriendly) {
    query.$and = query.$and || [];
    query.$and.push({
      $or: [
        { is_family_friendly: true },
        { familyScore: { $gte: 70 } },
        { tags: { $in: ['family-friendly', 'family', 'kids'] } }
      ]
    });
  }
  
  // Category filtering
  if (criteria.category) {
    query.$and = query.$and || [];
    query.$and.push({
      $or: [
        { category: criteria.category },
        { primary_category: criteria.category },
        { secondary_categories: criteria.category },
        { tags: criteria.category }
      ]
    });
  }
  
  return query;
}

// Fetch events with all relevant fields
async function fetchEventsForSearch(keywords) {
  const query = await buildMongoQuery(keywords);
  
  const events = await Event.find(query)
    .select({
      _id: 1,
      title: 1,
      description: 1,
      category: 1,
      primary_category: 1,
      secondary_categories: 1,
      start_date: 1,
      end_date: 1,
      status: 1,
      tags: 1,
      location: 1,
      address: 1,
      venue: 1,
      price: 1,
      pricing: 1,
      price_data: 1,
      familyScore: 1,
      is_family_friendly: 1,
      age_min: 1,
      age_max: 1,
      age_group: 1,
      age_restrictions: 1,
      target_audience: 1,
      event_url: 1,
      image_url: 1,
      venue_type: 1,
      indoor_outdoor: 1,
      event_type: 1
    })
    .limit(100)
    .sort({ start_date: 1 });
  
  return events;
}
```

## Response Processing

```javascript
function processAIResponse(aiResponse) {
  try {
    // Parse the structured response sections
    const sections = aiResponse.split(/\d+\.\s+[A-Z\s]+:/);
    
    const response = {
      interpretation: sections[1]?.trim(),
      filters: parseFilters(sections[2]),
      matchingEvents: parseMatchingEvents(sections[3]),
      summary: sections[4]?.trim(),
      noMatches: sections[5]?.trim()
    };
    
    // Sort events by relevance score
    if (response.matchingEvents) {
      response.matchingEvents.sort((a, b) => b.matchScore - a.matchScore);
    }
    
    return response;
  } catch (error) {
    console.error('Error parsing AI response:', error);
    return { error: 'Failed to parse search results' };
  }
}

function parseMatchingEvents(eventsText) {
  if (!eventsText) return [];
  
  // Extract individual event blocks
  const eventBlocks = eventsText.split(/Event ID:/);
  
  return eventBlocks.slice(1).map(block => {
    const lines = block.trim().split('\n');
    const event = {};
    
    lines.forEach(line => {
      if (line.includes('Event Title:')) {
        event.title = line.split('Event Title:')[1].trim();
      } else if (line.includes('Date/Time:')) {
        event.dateTime = line.split('Date/Time:')[1].trim();
      } else if (line.includes('Price:')) {
        event.price = line.split('Price:')[1].trim();
      } else if (line.includes('Location:')) {
        event.location = line.split('Location:')[1].trim();
      } else if (line.includes('Match Score:')) {
        event.matchScore = parseInt(line.match(/\d+/)?.[0] || 0);
      } else if (line.includes('Match Reason:')) {
        event.matchReason = line.split('Match Reason:')[1].trim();
      }
    });
    
    // Extract event ID from first line
    const idMatch = lines[0].match(/([a-f0-9]{24})/);
    if (idMatch) {
      event._id = idMatch[1];
    }
    
    return event;
  });
}
```

## Error Handling & Optimization

```javascript
async function searchEventsWithRetry(keywords, events, maxRetries = 2) {
  let attempt = 0;
  
  while (attempt < maxRetries) {
    try {
      // Optimize token usage by limiting events if too many
      let eventsToSend = events;
      if (events.length > 50) {
        // Pre-filter events based on basic criteria to reduce tokens
        const criteria = extractSearchCriteria(keywords);
        eventsToSend = preFilterEvents(events, criteria);
      }
      
      const result = await searchEvents(keywords, eventsToSend);
      return result;
      
    } catch (error) {
      attempt++;
      
      if (error.code === 'context_length_exceeded' && events.length > 20) {
        // Reduce number of events and retry
        events = events.slice(0, Math.floor(events.length / 2));
        console.log(`Reducing to ${events.length} events and retrying...`);
      } else if (attempt === maxRetries) {
        throw error;
      }
      
      // Wait before retry
      await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
    }
  }
}

// Pre-filter events to reduce token usage
function preFilterEvents(events, criteria) {
  return events.filter(event => {
    // Quick pre-filters based on extracted criteria
    if (criteria.price?.type === 'free' && 
        !event.price?.toLowerCase().includes('free') && 
        event.pricing?.base_price > 0) {
      return false;
    }
    
    if (criteria.location && 
        !event.venue?.area?.toLowerCase().includes(criteria.location.toLowerCase()) &&
        !event.location?.toLowerCase().includes(criteria.location.toLowerCase())) {
      return false;
    }
    
    return true;
  });
}
```

## Cost Optimization Tips

1. **Implement caching** for common queries:
```javascript
const queryCache = new Map();
const CACHE_TTL = 3600000; // 1 hour

async function searchWithCache(keywords, events) {
  const cacheKey = `${keywords}_${events.length}`;
  const cached = queryCache.get(cacheKey);
  
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.result;
  }
  
  const result = await searchEvents(keywords, events);
  queryCache.set(cacheKey, { result, timestamp: Date.now() });
  
  return result;
}
```

2. **Use embedding-based search** for semantic matching:
```javascript
// Generate embeddings for events on insert/update
async function generateEventEmbedding(event) {
  const text = `${event.title} ${event.description} ${event.tags?.join(' ')}`;
  
  const response = await openai.embeddings.create({
    model: "text-embedding-3-small",
    input: text
  });
  
  return response.data[0].embedding;
}

// Search using embeddings for better semantic matching
async function semanticSearch(query, limit = 20) {
  const queryEmbedding = await generateEventEmbedding({ title: query });
  
  // Use vector similarity search in MongoDB Atlas
  const events = await Event.aggregate([
    {
      $vectorSearch: {
        index: "event_embeddings",
        path: "embedding",
        queryVector: queryEmbedding,
        numCandidates: 100,
        limit: limit
      }
    }
  ]);
  
  return events;
}
```