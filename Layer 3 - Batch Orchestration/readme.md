# Layer 3 - Batch Orchestration

## Objective

Build a nightly batch pipeline that processes Silver data, creates Gold analytics,
and refreshes downstream search data.

## Architecture

Silver ADLS Gen2  
↓  
Azure Databricks  
↓  
Gold Delta Tables  
↓  
Azure Data Factory  
↓  
Search Index Refresh

## Gold Outputs

Three Gold Delta outputs are created:

- `sentiment_trends` – sentiment analysis by category and date.
- `top_entities` – frequently occurring entities by category/week.
- `trending_keywords` – key phrases over a 7-day window by category.

## Databricks

The `gold_layer_pipeline` notebook:

1. Reads Silver data from ADLS Gen2.
2. Maps articles to categories using URL hashes and raw filenames.
3. Generates the three Gold datasets.
4. Writes the results as Delta tables.
5. Uses MERGE-based processing for idempotent reruns.
6. Logs processing information using MLflow.

## Why MERGE?

MERGE prevents duplicate records when the same processing date is run again.
The idempotency test produced the same counts before and after rerun:

- Sentiment: `70 → 70`
- Entities: `4594 → 4594`
- Keywords: `7354 → 7354`

## Batch Orchestration

Azure Data Factory pipeline:

`Ingestion → Enrichment → Gold Aggregation → Search Index Refresh`

The Gold Aggregation activity triggers the Databricks job.

Retry policy:
- Retries: 2
- Retry interval: 60 seconds

## MLflow

MLflow records:

- Run date
- Article count
- Azure AI Language
- Embedding model: `text-embedding-3-small`

Successful run:
- Article count: `683`

## Result

Layer 3 provides scheduled batch orchestration, Gold Delta analytics,
idempotent processing, and MLflow tracking for downstream search and analytics.