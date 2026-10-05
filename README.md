# News NLP Pipeline on Azure

This project collects news articles, understands them using AI, and lets you search them through an API.

**Tools used:** Python, Azure Logic Apps, Event Grid, Azure Functions, Azure AI Language, Azure OpenAI, Azure Databricks, Azure Data Factory, Azure AI Search, Azure API Management

---

## How it works

```
NewsAPI
   ↓
Layer 1: Ingestion      → get the news and save it
   ↓
Layer 2: NLP Enrichment → add AI insights to each article
   ↓
Layer 3: Gold Analytics → calculate trends every night
   ↓
Layer 4: Search Index   → make articles searchable
   ↓
Layer 5: Search API     → let apps search the news
   ↓
Layer 6: Governance     → keep data tracked and safe
```

---

## Folder structure

```
Layer 1 - Ingestion/           Logic Apps + Functions
Layer 2 - NLP Enrichment/      Sample input and output
Layer 3 - Batch Orchestration/ Databricks notebook + Data Factory pipeline
Layer 4 - Indexing/            Search index and scripts
Layer 5 - API/                 Search API function
Layer 6/                       Governance notes
```



## Layer 1: Ingestion

**What it does:** Collects news and stores it exactly as received.

- 4 Logic Apps fetch news from NewsAPI, one for each category: technology, business, science and health.
- Each Logic App runs on a schedule (Recurrence trigger).
- The raw JSON is saved in Azure storage (`news/raw/`).
- When a new file arrives, Event Grid triggers two Azure Functions:
  - one starts the AI processing
  - one writes an audit log
- Each article's URL is turned into a SHA-256 hash and saved in a table (`ArticleDedup`). If the hash already exists, the article is skipped. This stops duplicates.

---

## Layer 2: NLP Enrichment

**What it does:** Adds AI insights to every article.

For each new article, the Azure Function:

1. Checks if it's a duplicate and skips it if so.
2. Sends it to Azure AI Language (5 articles at a time) to get:
   - **Sentiment** (positive, neutral or negative)
   - **Entities** (people, places, companies)
   - **Key phrases** (the main topics)
3. Asks Azure OpenAI to create an **embedding** (a list of 1536 numbers that captures the meaning of the article).
4. Saves the finished article in `news/silver/`.

If one article fails, the others still continue. The failed one is tried again next time.

---

## Layer 3: Gold Analytics

**What it does:** Every night, turns the articles into useful numbers.

- **Azure Data Factory** runs a nightly pipeline: Ingestion → Enrichment → Gold Aggregation → Search Index Refresh.
- The Gold step starts a **Databricks** notebook, which creates 3 tables:
  - `sentiment_trends`: how positive or negative the news is, by category and date
  - `top_entities`: the most mentioned names each week
  - `trending_keywords`: popular topics over the last 7 days
- Tables are saved in **Delta format** using **MERGE**.
- **MLflow** records each run (date, article count, models used).
- The Gold step retries 2 times, 60 seconds apart, if it fails.

Running the same day twice gives the same row counts, so there are no duplicates (Sentiment 70 → 70, Entities 4594 → 4594, Keywords 7354 → 7354).

---

## Layer 4: Search Index

**What it does:** Makes articles easy to find.

- Azure AI Search holds an index called `news-articles-index` with **861 articles**.
- It supports two kinds of search at once (hybrid search):
  - **Keyword search (BM25):** finds exact words
  - **Vector search (HNSW + cosine similarity):** finds similar meaning
- Results from both are combined using **Reciprocal Rank Fusion (RRF)**.

Scripts are in `Layer 4 - Indexing/search/`:

| File | What it does |
|---|---|
| `news-articles-index.json` | Defines the index |
| `upload_to_search.py` | Loads articles into the index |
| `hybrid_search.py` | Runs a hybrid search |

---

## Layer 5: Search API

**What it does:** Lets any app search the news.

- An Azure Function reads from the search index.
- **Azure API Management** sits in front of it and adds:
  - a rate limit of 10 calls per 60 seconds
  - API version `v1`

**Example request**

```
GET /searchnews?q=technology
```

**Example response**

```json
{
  "query": "technology",
  "count": 10,
  "results": [
    {
      "title": "...",
      "source": "...",
      "sentiment": "neutral",
      "entities": ["..."],
      "keyPhrases": ["..."],
      "score": 1.23
    }
  ]
}
```

If `q` is missing, the API returns an error (400).

---

## Layer 6: Governance

**What it does:** Keeps track of where data comes from and where it goes.

- Data is organised as Raw → Silver → Gold.
- Raw data is never changed, so it can be used for audits.
- Duplicate articles are blocked using the URL hash.
- The full data flow (lineage) is documented in `Layer 6/readme.md`.
- Microsoft Purview is the planned tool for scanning data, tracking lineage and flagging PII.

---

## Infrastructure

These are the Azure resources used in the project.

| Resource | Name / detail | Used for |
|---|---|---|
| Storage account (ADLS Gen2) | `news` container with `raw/` and `silver/` | Raw and enriched articles |
| Table Storage | `ArticleDedup` | Stores URL hashes to skip duplicates |
| Logic Apps (4) | tech, business, science, health | Fetching news on a schedule |
| Event Grid subscription | `BlobCreated` on the news container | Triggers the two functions |
| Function App | `func-news-nlp` | NLP enrichment |
| Function App | `func-news-audit` | Audit logging |
| Function App | `func-news-search` | Search API |
| Azure AI Language | Language resource | Sentiment, entities, key phrases |
| Azure OpenAI | `text-embedding-3-small` deployment | Embeddings |
| Azure Databricks | Notebook `gold_layer_pipeline`, job `gold-run` | Gold analytics |
| Azure Data Factory | `nlp-nightly-pipeline` | Nightly orchestration |
| Azure AI Search | `news-articles-index` | Hybrid search |
| Azure API Management | `News Search API`, version `v1` | Rate limiting and versioning |

Everything was created in the Azure Portal using an **Azure for Students** subscription.

---

## How to run it

### What you need

- An Azure account
- A free NewsAPI key
- Python 3.10 or 3.11
- Azure Functions Core Tools v4 and Azure CLI

### Step 1: Set up secrets

Never put real keys in your code. Copy the sample file and fill in your own values:

```
cd "Layer 4 - Indexing/search"
cp .env.sample .env
```

The `.env` file needs your Search endpoint and key, storage connection string, and OpenAI endpoint, key and embedding deployment name.

### Step 2: Ingestion

Create the 4 Logic Apps from `Layer 1 - Ingestion/logic-apps/`, add your NewsAPI key, and create an Event Grid subscription for `BlobCreated` events.

### Step 3: Deploy the functions

```
cd "Layer 1 - Ingestion/functions/func-news-nlp"
func azure functionapp publish YOUR_NLP_APP

cd "../func-news-audit"
func azure functionapp publish YOUR_AUDIT_APP
```

### Step 4: Gold layer

1. Import `gold_layer_pipeline.ipynb` into Databricks and run it.
2. Import `adf/nlp-nightly-pipeline.json` into Azure Data Factory.

### Step 5: Search index

```
cd "Layer 4 - Indexing/search"
pip install -r requirements.txt
python upload_to_search.py
python hybrid_search.py
```



## Questions asked in the case study, and what I chose

The case study asked a few "think about" questions for each layer. Here are the answers, and what I picked in this project.

### Layer 1: Ingestion

**Logic Apps or ADF HTTP?**
*I chose Logic Apps.* The job is just calling an API on a schedule, and Logic Apps is the simpler tool for that.

**Event Grid or Event Hub?**
*I chose Event Grid.* We react to a file being created, which is one event at a time. Event Hub is for constant, high-volume streams, which we don't have.

**How do you avoid saving the same article twice (idempotent ingestion)?**
*I hash each article URL (SHA-256) and store the hash in a table.* If the hash is already there, the article is skipped. Running the pipeline again gives the same result.

### Layer 2: NLP Enrichment

**What about batch size limits?**
*I chose batches of 5 articles* per call to Azure AI Language. It keeps requests small and well within service limits.

**What if part of a batch fails?**
*Each article's embedding is created separately,* so one failure doesn't stop the rest. Failed articles are not marked as done, so they are retried next run.

**How do you avoid scoring the same article again?**
*The URL hash table.* Articles already in the table are skipped, so we don't pay for the same AI calls twice.

**What does cosine similarity mean for embeddings?**
It measures the angle between two embeddings. A score close to 1 means the two articles have very similar meaning. *I used cosine as the metric in the search index.*

### Layer 3: Batch Orchestration

**How does Delta MERGE (upsert) work?**
MERGE compares new rows with existing rows. Matching rows are updated, and new rows are added. *I used MERGE for all 3 gold tables,* so re-running a day never creates duplicates.

**Why MLflow?**
It keeps a history of each run. *I log the run date, article count, the language service and the embedding model* (`text-embedding-3-small`).

**How do you make gold writes idempotent?**
The case study suggested `REPLACE WHERE`. *I chose MERGE instead.* Both give safe re-runs, and I tested it: same row counts before and after a re-run.

### Layer 4: Indexing

**When does hybrid search beat pure vector search?**
Vector search understands meaning but can miss exact names or words. Keyword search finds exact words but misses similar meaning. Hybrid uses both, so it handles both cases. *I used hybrid (BM25 + vector) with RRF.*

**What HNSW settings did I use?**
*Metric: cosine, m = 4, efConstruction = 400, efSearch = 500.* A higher efConstruction and efSearch means better accuracy but slower speed. That's fine for a small index of 861 articles.

**Why store full content in ADLS and not in Search?**
Search is for finding things fast. Storage is cheaper and is the main source of truth. *The index holds only the fields needed for search and results.*

### Layer 5: API Serving

**How would you check JWT tokens in API Management?**
With an inbound `validate-jwt` policy that checks the token before the request reaches the function. *I did not set this up in this project.*

**What is the API versioning strategy?**
*I chose path-based versioning (`v1`).* The version is part of the URL, so a future `v2` can run side by side without breaking `v1` users.

**How do caching and near-real-time indexing interact?**
A cache can show old results after new articles are indexed. A short cache time keeps results fresh enough. *I did not turn on caching,* so results are always live.

*I did add a rate limit of 10 calls per 60 seconds.*

### Layer 6: Governance

**How does ADF lineage differ from Databricks lineage in Purview?**
ADF lineage shows which pipeline moved data from one place to another. Databricks lineage can go deeper and show table and column level changes inside notebooks.

**Classification or sensitivity label?**
A classification describes what the data is (for example, "contains a person's name"). A sensitivity label controls how the data should be handled (for example, "Confidential").

**How do you export lineage from Purview?**
Through the Purview REST API.

*Purview was not available in my subscription, so I documented the lineage and design instead of deploying it.*

---

## Other design choices

**Why Raw, Silver and Gold?**
Raw keeps the original data, Silver holds the enriched data, and Gold holds the final analytics. If something breaks, you can rebuild each step from the one before.

**Why Azure Functions?**
They run only when needed, scale automatically, and you pay only for what you use.

**Why API Management?**
It protects the API with rate limiting and gives it a clean versioned URL.

---

## Limitations

- **Governance is design only.** Microsoft Purview was not available in the Azure for Students subscription. Storage scanning, automated lineage and PII classification are not implemented.
- **No PII flagging yet.** Articles are not marked as containing personal data.
- **The search API uses keyword search only.** The full hybrid search (keyword + vector) runs in the Layer 4 script, not in the API function.
- **API Management is basic.** It has rate limiting and versioning, but no JWT validation and no caching.
- **The search function is open.** It allows anonymous access, because API Management is meant to be the public entry point.
- **Some Data Factory steps are placeholders.** Ingestion, Enrichment and Search Index Refresh are simple wait steps. Only the Gold Aggregation step starts real work.
- **Free tier limits.** NewsAPI free allows 100 requests a day, and Azure for Students has a limited credit balance.

---

## Future improvements

- Deploy Microsoft Purview and add PII classifications
- Add the hybrid query to the API function
- Add JWT validation and caching in API Management
- Connect the Data Factory steps to the real functions and index refresh
- Add Power BI dashboards
- Add CI/CD with GitHub Actions

---

## Security tips

- Keep keys in environment variables or Azure app settings, not in code.
- Don't upload `.env` or `local.settings.json` to GitHub. Use the sample files instead.
