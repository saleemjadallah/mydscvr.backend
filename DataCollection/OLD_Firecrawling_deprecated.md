# Crawl

> Firecrawl can recursively search through a urls subdomains, and gather the content

Firecrawl efficiently crawls websites to extract comprehensive data while bypassing blockers. The process:

1. **URL Analysis:** Scans sitemap and crawls website to identify links
2. **Traversal:** Recursively follows links to find all subpages
3. **Scraping:** Extracts content from each page, handling JS and rate limits
4. **Output:** Converts data to clean markdown or structured format

This ensures thorough data collection from any starting URL.

## Crawling

### /crawl endpoint

Used to crawl a URL and all accessible subpages. This submits a crawl job and returns a job ID to check the status of the crawl.

<Warning>By default - Crawl will ignore sublinks of a page if they aren't children of the url you provide. So, the website.com/other-parent/blog-1 wouldn't be returned if you crawled website.com/blogs/. If you want website.com/other-parent/blog-1, use the `allowBackwardLinks` parameter</Warning>

### Installation

<CodeGroup>
  ```bash Python
  pip install firecrawl-py
  ```

  ```bash Node
  npm install @mendable/firecrawl-js
  ```

  ```bash Go
  go get github.com/mendableai/firecrawl-go
  ```

  ```yaml Rust
  # Add this to your Cargo.toml
  [dependencies]
  firecrawl = "^1.0"
  tokio = { version = "^1", features = ["full"] }
  ```
</CodeGroup>

### Usage

<CodeGroup>
  ```python Python
  from firecrawl import FirecrawlApp, ScrapeOptions

  app = FirecrawlApp(api_key="fc-YOUR_API_KEY")

  # Crawl a website:
  crawl_result = app.crawl_url(
    'https://firecrawl.dev', 
    limit=10, 
    scrape_options=ScrapeOptions(formats=['markdown', 'html']),
  )
  print(crawl_result)
  ```

  ```js Node
  import FirecrawlApp from '@mendable/firecrawl-js';

  const app = new FirecrawlApp({apiKey: "fc-YOUR_API_KEY"});

  const crawlResponse = await app.crawlUrl('https://firecrawl.dev', {
    limit: 100,
    scrapeOptions: {
      formats: ['markdown', 'html'],
    }
  })

  if (!crawlResponse.success) {
    throw new Error(`Failed to crawl: ${crawlResponse.error}`)
  }

  console.log(crawlResponse)
  ```

  ```go Go
  import (
  	"fmt"
  	"log"

  	"github.com/mendableai/firecrawl-go"
  )

  func main() {
  	// Initialize the FirecrawlApp with your API key
  	apiKey := "fc-YOUR_API_KEY"
  	apiUrl := "https://api.firecrawl.dev"
  	version := "v1"

  	app, err := firecrawl.NewFirecrawlApp(apiKey, apiUrl, version)
  	if err != nil {
  		log.Fatalf("Failed to initialize FirecrawlApp: %v", err)
  	}

  	// Crawl a website
  	crawlStatus, err := app.CrawlUrl("https://firecrawl.dev", map[string]any{
  		"limit": 100,
  		"scrapeOptions": map[string]any{
  			"formats": []string{"markdown", "html"},
  		},
  	})
  	if err != nil {
  		log.Fatalf("Failed to send crawl request: %v", err)
  	}

  	fmt.Println(crawlStatus) 
  }
  ```

  ```rust Rust
  use firecrawl::{crawl::{CrawlOptions, CrawlScrapeOptions, CrawlScrapeFormats}, FirecrawlApp};

  #[tokio::main]
  async fn main() {
      // Initialize the FirecrawlApp with the API key
      let app = FirecrawlApp::new("fc-YOUR_API_KEY").expect("Failed to initialize FirecrawlApp");

      // Crawl a website
      let crawl_options = CrawlOptions {
          scrape_options: CrawlScrapeOptions {
              formats: vec![ CrawlScrapeFormats::Markdown, CrawlScrapeFormats::HTML ].into(),
              ..Default::default()
          }.into(),
          limit: 100.into(),
          ..Default::default()
      };

      let crawl_result = app
          .crawl_url("https://mendable.ai", crawl_options)
          .await;

      match crawl_result {
          Ok(data) => println!("Crawl Result (used {} credits):\n{:#?}", data.credits_used, data.data),
          Err(e) => eprintln!("Crawl failed: {}", e),
      }
  }
  ```

  ```bash cURL
  curl -X POST https://api.firecrawl.dev/v1/crawl \
      -H 'Content-Type: application/json' \
      -H 'Authorization: Bearer YOUR_API_KEY' \
      -d '{
        "url": "https://docs.firecrawl.dev",
        "limit": 100,
        "scrapeOptions": {
          "formats": ["markdown", "html"]
        }
      }'
  ```
</CodeGroup>

### API Response

If you're using cURL or `async crawl` functions on SDKs, this will return an `ID` where you can use to check the status of the crawl.

<Note>If you're using the SDK, check the SDK response section [below](#sdk-response).</Note>

```json
{
  "success": true,
  "id": "123-456-789",
  "url": "https://api.firecrawl.dev/v1/crawl/123-456-789"
}
```

### Check Crawl Job

Used to check the status of a crawl job and get its result.

<Note>This endpoint only works for crawls that are in progress or crawls that have completed recently. </Note>

<CodeGroup>
  ```python Python
  crawl_status = app.check_crawl_status("<crawl_id>")
  print(crawl_status)
  ```

  ```js Node
  const crawlResponse = await app.checkCrawlStatus("<crawl_id>");

  if (!crawlResponse.success) {
    throw new Error(`Failed to check crawl status: ${crawlResponse.error}`)
  }

  console.log(crawlResponse)
  ```

  ```go Go
  // Get crawl status
  crawlStatus, err := app.CheckCrawlStatus("<crawl_id>")

  if err != nil {
    log.Fatalf("Failed to get crawl status: %v", err)
  }

  fmt.Println(crawlStatus)
  ```

  ```rust Rust
  let crawl_status = app.check_crawl_status(crawl_id).await;

  match crawl_status {
      Ok(data) => println!("Crawl Status:\n{:#?}", data),
      Err(e) => eprintln!("Check crawl status failed: {}", e),
  }
  ```

  ```bash cURL
  curl -X GET https://api.firecrawl.dev/v1/crawl/<crawl_id> \
      -H 'Content-Type: application/json' \
      -H 'Authorization: Bearer YOUR_API_KEY'
  ```
</CodeGroup>

#### Response Handling

The response varies based on the crawl's status.

For not completed or large responses exceeding 10MB, a `next` URL parameter is provided. You must request this URL to retrieve the next 10MB of data. If the `next` parameter is absent, it indicates the end of the crawl data.

The skip parameter sets the maximum number of results returned for each chunk of results returned.

<Info>
  The skip and next parameter are only relavent when hitting the api directly. If you're using the SDK, we handle this for you and will return all the results at once.
</Info>

<CodeGroup>
  ```json Scraping
  {
    "status": "scraping",
    "total": 36,
    "completed": 10,
    "creditsUsed": 10,
    "expiresAt": "2024-00-00T00:00:00.000Z",
    "next": "https://api.firecrawl.dev/v1/crawl/123-456-789?skip=10",
    "data": [
      {
        "markdown": "[Firecrawl Docs home page![light logo](https://mintlify.s3-us-west-1.amazonaws.com/firecrawl/logo/light.svg)!...",
        "html": "<!DOCTYPE html><html lang=\"en\" class=\"js-focus-visible lg:[--scroll-mt:9.5rem]\" data-js-focus-visible=\"\">...",
        "metadata": {
          "title": "Build a 'Chat with website' using Groq Llama 3 | Firecrawl",
          "language": "en",
          "sourceURL": "https://docs.firecrawl.dev/learn/rag-llama3",
          "description": "Learn how to use Firecrawl, Groq Llama 3, and Langchain to build a 'Chat with your website' bot.",
          "ogLocaleAlternate": [],
          "statusCode": 200
        }
      },
      ...
    ]
  }
  ```

  ```json Completed
  {
    "status": "completed",
    "total": 36,
    "completed": 36,
    "creditsUsed": 36,
    "expiresAt": "2024-00-00T00:00:00.000Z",
    "next": "https://api.firecrawl.dev/v1/crawl/123-456-789?skip=26",
    "data": [
      {
        "markdown": "[Firecrawl Docs home page![light logo](https://mintlify.s3-us-west-1.amazonaws.com/firecrawl/logo/light.svg)!...",
        "html": "<!DOCTYPE html><html lang=\"en\" class=\"js-focus-visible lg:[--scroll-mt:9.5rem]\" data-js-focus-visible=\"\">...",
        "metadata": {
          "title": "Build a 'Chat with website' using Groq Llama 3 | Firecrawl",
          "language": "en",
          "sourceURL": "https://docs.firecrawl.dev/learn/rag-llama3",
          "description": "Learn how to use Firecrawl, Groq Llama 3, and Langchain to build a 'Chat with your website' bot.",
          "ogLocaleAlternate": [],
          "statusCode": 200
        }
      },
      ...
    ]
  }
  ```
</CodeGroup>

### SDK Response

The SDK provides two ways to crawl URLs:

1. **Synchronous Crawling** (`crawl_url`/`crawlUrl`):
   * Waits for the crawl to complete and returns the full response
   * Handles pagination automatically
   * Recommended for most use cases

<CodeGroup>
  ```python Python
  from firecrawl import FirecrawlApp, ScrapeOptions

  app = FirecrawlApp(api_key="fc-YOUR_API_KEY")

  # Crawl a website:
  crawl_status = app.crawl_url(
    'https://firecrawl.dev', 
    limit=100, 
    scrape_options=ScrapeOptions(formats=['markdown', 'html']),
    poll_interval=30
  )
  print(crawl_status)
  ```

  ```js Node
  import FirecrawlApp from '@mendable/firecrawl-js';

  const app = new FirecrawlApp({apiKey: "fc-YOUR_API_KEY"});

  const crawlResponse = await app.crawlUrl('https://firecrawl.dev', {
    limit: 100,
    scrapeOptions: {
      formats: ['markdown', 'html'],
    }
  })

  if (!crawlResponse.success) {
    throw new Error(`Failed to crawl: ${crawlResponse.error}`)
  }

  console.log(crawlResponse)
  ```
</CodeGroup>

The response includes the crawl status and all scraped data:

<CodeGroup>
  ```bash Python
  success=True
  status='completed'
  completed=100
  total=100
  creditsUsed=100
  expiresAt=datetime.datetime(2025, 4, 23, 19, 21, 17, tzinfo=TzInfo(UTC))
  next=None
  data=[
    FirecrawlDocument(
      markdown='[Day 7 - Launch Week III.Integrations DayApril 14th to 20th](...',
      metadata={
        'title': '15 Python Web Scraping Projects: From Beginner to Advanced',
        ...
        'scrapeId': '97dcf796-c09b-43c9-b4f7-868a7a5af722',
        'sourceURL': 'https://www.firecrawl.dev/blog/python-web-scraping-projects',
        'url': 'https://www.firecrawl.dev/blog/python-web-scraping-projects',
        'statusCode': 200
      }
    ),
    ...
  ]
  ```

  ```json Node
  {
    success: true,
    status: "completed",
    completed: 100,
    total: 100,
    creditsUsed: 100,
    expiresAt: "2025-04-23T19:28:45.000Z",
    data: [
      {
        markdown: "[Day 7 - Launch Week III.Integrations DayApril ...",
        html: `<!DOCTYPE html><html lang="en" class="light" style="color...`,
        metadata: [Object],
      },
      ...
    ]
  }
  ```
</CodeGroup>

2. **Asynchronous Crawling** (`async_crawl_url`/`asyncCrawlUrl`):
   * Returns immediately with a crawl ID
   * Allows manual status checking
   * Useful for long-running crawls or custom polling logic

<CodeGroup>
  <AsyncCrawlPython />

  <AsyncCrawlNode />
</CodeGroup>

## Crawl WebSocket

Firecrawl's WebSocket-based method, `Crawl URL and Watch`, enables real-time data extraction and monitoring. Start a crawl with a URL and customize it with options like page limits, allowed domains, and output formats, ideal for immediate data processing needs.

<CodeGroup>
  ```python Python
  # inside an async function...
  nest_asyncio.apply()

  # Define event handlers
  def on_document(detail):
      print("DOC", detail)

  def on_error(detail):
      print("ERR", detail['error'])

  def on_done(detail):
      print("DONE", detail['status'])

      # Function to start the crawl and watch process
  async def start_crawl_and_watch():
      # Initiate the crawl job and get the watcher
      watcher = app.crawl_url_and_watch('firecrawl.dev', limit=5)

      # Add event listeners
      watcher.add_event_listener("document", on_document)
      watcher.add_event_listener("error", on_error)
      watcher.add_event_listener("done", on_done)

      # Start the watcher
      await watcher.connect()

  # Run the event loop
  await start_crawl_and_watch()
  ```

  ```js Node
  const watch = await app.crawlUrlAndWatch('mendable.ai', { excludePaths: ['blog/*'], limit: 5});

  watch.addEventListener("document", doc => {
    console.log("DOC", doc.detail);
  });

  watch.addEventListener("error", err => {
    console.error("ERR", err.detail.error);
  });

  watch.addEventListener("done", state => {
    console.log("DONE", state.detail.status);
  });
  ```
</CodeGroup>

## Crawl Webhook

You can configure webhooks to receive real-time notifications as your crawl progresses. This allows you to process pages as they're scraped instead of waiting for the entire crawl to complete.

```bash cURL
curl -X POST https://api.firecrawl.dev/v1/crawl \
    -H 'Content-Type: application/json' \
    -H 'Authorization: Bearer YOUR_API_KEY' \
    -d '{
      "url": "https://docs.firecrawl.dev",
      "limit": 100,
      "webhook": {
        "url": "https://your-domain.com/webhook",
        "metadata": {
          "any_key": "any_value"
        },
        "events": ["started", "page", "completed"]
      }
    }'
```

For comprehensive webhook documentation including event types, payload structure, and implementation examples, see the [Webhooks documentation](/features/webhooks).

### Quick Reference

**Event Types:**

* `crawl.started` - When the crawl begins
* `crawl.page` - For each page successfully scraped
* `crawl.completed` - When the crawl finishes
* `crawl.failed` - If the crawl encounters an error

**Basic Payload:**

```json
{
  "success": true,
  "type": "crawl.page",
  "id": "crawl-job-id",
  "data": [...], // Page data for 'page' events
  "metadata": {}, // Your custom metadata
  "error": null
}
```

<Note>
  For detailed webhook configuration, security best practices, and troubleshooting, visit the [Webhooks documentation](/features/webhooks).
</Note>
# JSON mode - LLM Extract

> Extract structured data from pages via LLMs

## Scrape and extract structured data with Firecrawl

{/* <Warning>Scrape LLM Extract will be deprecated in future versions. Please use the new [Extract](/features/extract) endpoint.</Warning> */}

Firecrawl uses AI to get structured data from web pages in 3 steps:

1. **Set the Schema:**
   Tell us what data you want by defining a JSON schema (using OpenAI's format) along with the webpage URL.

2. **Make the Request:**
   Send your URL and schema to our scrape endpoint. See how here:
   [Scrape Endpoint Documentation](https://docs.firecrawl.dev/api-reference/endpoint/scrape)

3. **Get Your Data:**
   Get back clean, structured data matching your schema that you can use right away.

This makes getting web data in the format you need quick and easy.

## Extract structured data

### /scrape (with json) endpoint

Used to extract structured data from scraped pages.

<CodeGroup>
  ```python Python
  from firecrawl import JsonConfig, FirecrawlApp
  from pydantic import BaseModel
  app = FirecrawlApp(api_key="<YOUR_API_KEY>")

  class ExtractSchema(BaseModel):
      company_mission: str
      supports_sso: bool
      is_open_source: bool
      is_in_yc: bool

  json_config = JsonConfig(
      schema=ExtractSchema
  )

  llm_extraction_result = app.scrape_url(
      'https://firecrawl.dev',
      formats=["json"],
      json_options=json_config,
      only_main_content=False,
      timeout=120000
  )

  print(llm_extraction_result.json)
  ```

  ```js Node
  import FirecrawlApp from "@mendable/firecrawl-js";
  import { z } from "zod";

  const app = new FirecrawlApp({
    apiKey: "fc-YOUR_API_KEY"
  });

  // Define schema to extract contents into
  const schema = z.object({
    company_mission: z.string(),
    supports_sso: z.boolean(),
    is_open_source: z.boolean(),
    is_in_yc: z.boolean()
  });

  const scrapeResult = await app.scrapeUrl("https://docs.firecrawl.dev/", {
    formats: ["json"],
    jsonOptions: { schema: schema }
  });

  if (!scrapeResult.success) {
    throw new Error(`Failed to scrape: ${scrapeResult.error}`)
  }

  console.log(scrapeResult.json);
  ```

  ```bash cURL
  curl -X POST https://api.firecrawl.dev/v1/scrape \
      -H 'Content-Type: application/json' \
      -H 'Authorization: Bearer YOUR_API_KEY' \
      -d '{
        "url": "https://docs.firecrawl.dev/",
        "formats": ["json"],
        "jsonOptions": {
          "schema": {
            "type": "object",
            "properties": {
              "company_mission": {
                        "type": "string"
              },
              "supports_sso": {
                        "type": "boolean"
              },
              "is_open_source": {
                        "type": "boolean"
              },
              "is_in_yc": {
                        "type": "boolean"
              }
            },
            "required": [
              "company_mission",
              "supports_sso",
              "is_open_source",
              "is_in_yc"
            ]
          }
        }
      }'
  ```
</CodeGroup>

Output:

```json JSON
{
    "success": true,
    "data": {
      "json": {
        "company_mission": "AI-powered web scraping and data extraction",
        "supports_sso": true,
        "is_open_source": true,
        "is_in_yc": true
      },
      "metadata": {
        "title": "Firecrawl",
        "description": "AI-powered web scraping and data extraction",
        "robots": "follow, index",
        "ogTitle": "Firecrawl",
        "ogDescription": "AI-powered web scraping and data extraction",
        "ogUrl": "https://firecrawl.dev/",
        "ogImage": "https://firecrawl.dev/og.png",
        "ogLocaleAlternate": [],
        "ogSiteName": "Firecrawl",
        "sourceURL": "https://firecrawl.dev/"
      },
    }
}
```

### Extracting without schema (New)

You can now extract without a schema by just passing a `prompt` to the endpoint. The llm chooses the structure of the data.

<CodeGroup>
  ```bash cURL
  curl -X POST https://api.firecrawl.dev/v1/scrape \
      -H 'Content-Type: application/json' \
      -H 'Authorization: Bearer YOUR_API_KEY' \
      -d '{
        "url": "https://docs.firecrawl.dev/",
        "formats": ["json"],
        "jsonOptions": {
          "prompt": "Extract the company mission from the page."
        }
      }'
  ```
</CodeGroup>

Output:

```json JSON
{
    "success": true,
    "data": {
      "json": {
        "company_mission": "AI-powered web scraping and data extraction",
      },
      "metadata": {
        "title": "Firecrawl",
        "description": "AI-powered web scraping and data extraction",
        "robots": "follow, index",
        "ogTitle": "Firecrawl",
        "ogDescription": "AI-powered web scraping and data extraction",
        "ogUrl": "https://firecrawl.dev/",
        "ogImage": "https://firecrawl.dev/og.png",
        "ogLocaleAlternate": [],
        "ogSiteName": "Firecrawl",
        "sourceURL": "https://firecrawl.dev/"
      },
    }
}
```

### JSON options object

The `jsonOptions` object accepts the following parameters:

* `schema`: The schema to use for the extraction.
* `systemPrompt`: The system prompt to use for the extraction.
* `prompt`: The prompt to use for the extraction without a schema.
# Change Tracking with Crawl

> Track changes across your entire website, including new, removed, and hidden pages

Change tracking becomes even more powerful when combined with crawling. While change tracking on individual pages shows you content changes, using it with crawl lets you monitor your entire website structure - showing new pages, removed pages, and pages that have become hidden.

## Basic Usage

To enable change tracking during a crawl, include it in the `formats` array of your `scrapeOptions`:

```typescript
// JavaScript/TypeScript
const app = new FirecrawlApp({ apiKey: 'your-api-key' });
const result = await app.crawl('https://example.com', {
  scrapeOptions: {
    formats: ['markdown', 'changeTracking']
  }
});
```

```python
# Python
app = FirecrawlApp(api_key='your-api-key')
result = app.crawl('https://firecrawl.dev', {
    'scrapeOptions': {
        'formats': ['markdown', 'changeTracking']
    }
})
```

```json
{
  "success": true,
  "status": "completed",
  "completed": 2,
  "total": 2,
  "creditsUsed": 2,
  "expiresAt": "2025-04-14T18:44:13.000Z",
  "data": [
    {
      "markdown": "# Turn websites into LLM-ready data\n\nPower your AI apps with clean data crawled from any website...",
      "metadata": {},
      "changeTracking": {
        "previousScrapeAt": "2025-04-10T12:00:00Z",
        "changeStatus": "changed",
        "visibility": "visible"
      }
    },
    {
      "markdown": "## Flexible Pricing\n\nStart for free, then scale as you grow...",
      "metadata": {},
      "changeTracking": {
        "previousScrapeAt": "2025-04-10T12:00:00Z",
        "changeStatus": "changed",
        "visibility": "visible"
      }
    }
  ]
}
```

## Understanding Change Status

When using change tracking with crawl, the `changeStatus` field becomes especially valuable:

* `new`: A page that didn't exist in your previous crawl
* `same`: A page that exists and hasn't changed since your last crawl
* `changed`: A page that exists but has been modified since your last crawl
* `removed`: A page that existed in your previous crawl but is no longer found

## Page Visibility

The `visibility` field helps you understand how pages are discovered:

* `visible`: The page is discoverable through links or the sitemap
* `hidden`: The page still exists but is no longer linked or in the sitemap

This is particularly useful for:

* Detecting orphaned content
* Finding pages accidentally removed from navigation
* Monitoring site structure changes
* Identifying content that should be re-linked or removed

## Full Diff Support

For detailed change tracking with diffs, you can use the same options as described in the [Change Tracking for Scrape](/features/change-tracking) documentation.
