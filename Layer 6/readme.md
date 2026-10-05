# Layer 6 – Governance

## Overview

Designed the governance layer for data discovery, lineage, and PII classification using Microsoft Purview.

## Planned Governance

The planned governance flow covers:

- ADLS Gen2 raw, silver, and gold data
- Data lineage from raw JSON to processed data and Azure AI Search
- Data asset discovery and scanning
- PII identification using custom classifications

## Implementation Status

Microsoft Purview was evaluated for this layer but was **not available in the Azure for Students subscription** used for this project.

Therefore:

- Purview account: Not deployed
- Storage scanning: Not implemented
- PII classification: Not implemented
- Automated lineage: Not implemented

## Data Flow

```text
NewsAPI
   ↓
Logic Apps
   ↓
ADLS Gen2 – Raw
   ↓
Azure Functions – NLP
   ↓
ADLS Gen2 – Silver
   ↓
Databricks – Gold
   ↓
Azure AI Search
   ↓
Search API / APIM