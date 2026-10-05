# Layer 4 – Indexing

## Overview

Index enriched news articles in Azure AI Search and enable hybrid keyword + vector retrieval.

## Azure Services

- Azure AI Search
- Azure OpenAI (`text-embedding-3-small`)
- Azure Blob Storage / ADLS Gen2

## Implementation

- Created `news-articles-index` in Azure AI Search.
- Configured article metadata fields and a 1536-dimensional embedding field.
- Configured HNSW vector search with cosine similarity.
- Loaded 861 enriched articles into the index with 0 failures.
- Used SHA-256 URL hashes as valid Search document keys.
- Implemented hybrid BM25 + vector search.
- Azure AI Search combines results using Reciprocal Rank Fusion (RRF).
- Validated hybrid search with ranked results.

## Validation

- 861 documents indexed successfully.
- Hybrid search returned 10 ranked results.
- BM25 + HNSW + cosine similarity + RRF verified.

## Security

- Credentials stored in `.env`.
- `.env` excluded from GitHub.
- `.env.sample` contains placeholders only.

## Outcome

Azure AI Search is ready to provide hybrid retrieval for the Layer 5 Search API.