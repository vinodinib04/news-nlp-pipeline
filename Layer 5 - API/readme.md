# Layer 5 – Search API & API Management

## Overview

Built a serverless search API for news articles using Azure Functions and Azure API Management.

## Azure Services

- Azure Functions
- Azure AI Search
- Azure API Management

## Implementation

- Created a separate `func-news-search` Function App.
- Implemented the HTTP `searchnews` endpoint.
- Added the `q` query parameter for search queries.
- Connected the Function to the `news-articles-index` in Azure AI Search.
- Created the `News Search API` in Azure API Management.
- Tested the APIM → Function → Azure AI Search flow successfully.
- Configured rate limiting to **10 calls per 60 seconds**.
- Implemented path-based API versioning using **v1**.

## Validation

- Function search returned news articles successfully.
- APIM test returned **HTTP 200 OK**.
- Rate-limit policy configured.
- API version `v1` configured.

## Security

- Credentials stored in Azure application settings and local environment variables.
- `local.settings.json` is excluded from GitHub.
- `local.settings.sample.json` contains placeholders only.

## Outcome

A versioned and rate-limited Search API is available through Azure API Management for querying the Azure AI Search news index.