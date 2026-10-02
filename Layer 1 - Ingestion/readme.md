# Layer 1 – News Ingestion

## Overview
Layer 1 collects news articles from NewsAPI and stores the raw API response
in Azure Blob Storage for downstream NLP processing.

## Flow
NewsAPI → Logic Apps → Blob Storage → Event Grid → Azure Functions

## Components

- **Logic Apps:** Four scheduled workflows fetch news for technology, health,
  business, and science categories.

- **Blob Storage:** Stores the original NewsAPI JSON response in the
  `news/raw/` path. This acts as the raw landing zone.

- **Event Grid:** Detects `BlobCreated` events and triggers two Functions:
  one for NLP processing and one for audit logging.

- **NLP Function:** Reads the articles from the raw JSON and checks whether
  each article has already been processed.

- **Audit Function:** Records Blob Storage events for monitoring and auditing.

- **Azure Table Storage:** The `ArticleDedup` table stores a SHA-256 hash of
  each article URL. Existing hashes are treated as duplicates and skipped.

## Key Design Decisions

**Logic Apps vs ADF:**  
Logic Apps was selected because the requirement is mainly scheduled HTTP-based
API ingestion.

**Event Grid vs Event Hub:**  
Event Grid was selected because the trigger is a Blob Storage event rather than
continuous event streaming.

**Idempotency:**  
Article URLs are hashed using SHA-256 and the hash is used as the
deduplication key. This prevents the same article from being processed twice.

## Result

Layer 1 provides scheduled ingestion, raw data storage, event-driven
processing, audit logging, and duplicate detection.