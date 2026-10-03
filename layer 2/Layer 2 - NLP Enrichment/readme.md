# Layer 2 – NLP Enrichment

## Objective
Enrich raw NewsAPI articles with NLP results and vector embeddings for downstream analytics and search.

## Flow

news/raw/
    ↓
Azure Function (processnewsnlp)
    ↓
Azure AI Language
    ├── Sentiment Analysis
    ├── Entity Recognition
    └── Key Phrase Extraction
    ↓
Azure OpenAI
(text-embedding-3-small)
    ↓
news/silver/

## Components

- **Azure Function:** Reads raw articles and performs NLP enrichment.
- **Azure AI Language:** Performs sentiment, entity recognition, and key phrase extraction.
- **Azure OpenAI:** Generates vector embeddings using `text-embedding-3-small`.
- **Azure Table Storage:** Stores SHA-256 article URL hashes for deduplication.
- **Azure Blob Storage:** Stores enriched articles in `news/silver/`.

## Processing

1. Read articles from `news/raw/`.
2. Generate SHA-256 hash from each article URL.
3. Skip duplicate articles.
4. Process new articles in batches of 5.
5. Generate embeddings using Azure OpenAI.
6. Combine the NLP results and embeddings with the article data.
7. Write enriched data to `news/silver/`.

## Output

Each enriched article contains:

- `url`
- `title`
- `description`
- `sentiment`
- `entities`
- `keyPhrases`
- `embedding`

## Result

Layer 2 converts raw news articles into AI-enriched silver data
containing NLP insights and vector embeddings for downstream
analytics and search.