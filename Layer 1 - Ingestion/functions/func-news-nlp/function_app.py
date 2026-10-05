import logging
import hashlib
import json
import os
from datetime import datetime, timezone

import azure.functions as func
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI


app = func.FunctionApp()


# =========================================================
# STORAGE
# =========================================================

def get_storage_connection_string():
    connection_string = os.environ.get(
        "NEWS_STORAGE_CONNECTION_STRING"
    )

    if not connection_string:
        raise RuntimeError(
            "NEWS_STORAGE_CONNECTION_STRING is not configured."
        )

    return connection_string


def get_dedup_table():
    connection_string = get_storage_connection_string()

    table_service = TableServiceClient.from_connection_string(
        connection_string
    )

    return table_service.get_table_client(
        table_name="ArticleDedup"
    )


def get_blob_service():
    return BlobServiceClient.from_connection_string(
        get_storage_connection_string()
    )


def get_blob_content(blob_url):
    """
    Download raw NewsAPI JSON from Blob Storage.
    """

    marker = ".blob.core.windows.net/"

    if marker not in blob_url:
        raise ValueError(
            f"Unexpected blob URL: {blob_url}"
        )

    container_and_blob = blob_url.split(
        marker,
        1
    )[1]

    parts = container_and_blob.split(
        "/",
        1
    )

    if len(parts) != 2:
        raise ValueError(
            f"Could not determine container/blob from URL: {blob_url}"
        )

    container_name = parts[0]
    blob_name = parts[1]

    logging.info(
        "Reading container: %s",
        container_name
    )

    logging.info(
        "Reading blob: %s",
        blob_name
    )

    blob_client = get_blob_service().get_blob_client(
        container=container_name,
        blob=blob_name
    )

    return blob_client.download_blob().readall()


# =========================================================
# AZURE AI LANGUAGE
# =========================================================

def get_language_client():

    endpoint = os.environ.get(
        "LANGUAGE_ENDPOINT"
    )

    key = os.environ.get(
        "LANGUAGE_KEY"
    )

    if not endpoint or not key:
        raise RuntimeError(
            "Language API settings are not configured."
        )

    return TextAnalyticsClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key)
    )


# =========================================================
# AZURE OPENAI
# =========================================================

def get_openai_client():

    endpoint = os.environ.get(
        "AZURE_OPENAI_ENDPOINT"
    )

    key = os.environ.get(
        "AZURE_OPENAI_KEY"
    )

    if not endpoint or not key:
        raise RuntimeError(
            "Azure OpenAI settings are not configured."
        )

    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=key,
        api_version="2024-10-21"
    )


# =========================================================
# TEXT PREPARATION
# =========================================================

def get_article_text(article):

    title = article.get(
        "title",
        ""
    ) or ""

    description = article.get(
        "description",
        ""
    ) or ""

    content = article.get(
        "content",
        ""
    ) or ""

    return f"{title}\n{description}\n{content}".strip()


# =========================================================
# LANGUAGE ENRICHMENT
# =========================================================

def enrich_with_language(articles):

    language_client = get_language_client()

    texts = [
        get_article_text(article)
        for article in articles
    ]

    # Empty articles are handled separately.
    valid_indexes = [
        index
        for index, text in enumerate(texts)
        if text
    ]

    results = {}

    # Azure AI Language requests are processed in batches.
    batch_size = 5

    for start in range(
        0,
        len(valid_indexes),
        batch_size
    ):

        batch_indexes = valid_indexes[
            start:start + batch_size
        ]

        batch_texts = [
            texts[index]
            for index in batch_indexes
        ]

        logging.info(
            "Processing Language batch: %d articles",
            len(batch_texts)
        )

        sentiment_results = (
            language_client.analyze_sentiment(
                batch_texts
            )
        )

        entity_results = (
            language_client.recognize_entities(
                batch_texts
            )
        )

        key_phrase_results = (
            language_client.extract_key_phrases(
                batch_texts
            )
        )

        for position, article_index in enumerate(
            batch_indexes
        ):

            sentiment = sentiment_results[
                position
            ]

            entities = entity_results[
                position
            ]

            key_phrases = key_phrase_results[
                position
            ]

            if sentiment.is_error:
                sentiment_value = ""
            else:
                sentiment_value = sentiment.sentiment

            if entities.is_error:
                entity_values = []
            else:
                entity_values = [
                    entity.text
                    for entity in entities.entities
                ]

            if key_phrases.is_error:
                phrase_values = []
            else:
                phrase_values = list(
                    key_phrases.key_phrases
                )

            results[article_index] = {
                "sentiment": sentiment_value,
                "entities": entity_values,
                "key_phrases": phrase_values
            }

    return results


# =========================================================
# AZURE OPENAI EMBEDDINGS
# =========================================================

def generate_embeddings(articles):

    openai_client = get_openai_client()

    deployment_name = os.environ.get(
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
    )

    if not deployment_name:
        raise RuntimeError(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT is not configured."
        )

    embeddings = {}

    for index, article in enumerate(articles):

        text = get_article_text(article)

        if not text:
            embeddings[index] = []
            continue

        try:

            response = openai_client.embeddings.create(
                model=deployment_name,
                input=text
            )

            embeddings[index] = (
                response.data[0].embedding
            )

            logging.info(
                "Embedding generated for article %d",
                index + 1
            )

        except Exception as e:

            logging.error(
                "Embedding failed for article %d: %s",
                index + 1,
                str(e)
            )

            embeddings[index] = []

    return embeddings


# =========================================================
# WRITE SILVER DATA
# =========================================================

def write_silver_data(
    blob_url,
    enriched_articles
):

    marker = ".blob.core.windows.net/"

    container_and_blob = blob_url.split(
        marker,
        1
    )[1]

    parts = container_and_blob.split(
        "/",
        1
    )

    raw_container = parts[0]
    raw_blob_name = parts[1]

    # We use the same news container and create
    # a silver virtual directory.
    silver_container = raw_container

    filename = raw_blob_name.split("/")[-1]

    silver_blob_name = (
        f"silver/{filename}"
    )

    silver_data = {
        "processedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "sourceBlob": blob_url,

        "articles": enriched_articles
    }

    blob_client = get_blob_service().get_blob_client(
        container=silver_container,
        blob=silver_blob_name
    )

    blob_client.upload_blob(
        json.dumps(
            silver_data,
            ensure_ascii=False
        ).encode("utf-8"),

        overwrite=True
    )

    logging.info(
        "Silver data written to: %s",
        silver_blob_name
    )


# =========================================================
# EVENT GRID FUNCTION
# =========================================================

@app.event_grid_trigger(
    arg_name="azeventgrid"
)
def processnewsnlp(
    azeventgrid: func.EventGridEvent
):

    logging.info(
        "Python EventGrid trigger processed an event"
    )

    logging.info(
        "Event subject: %s",
        azeventgrid.subject
    )

    logging.info(
        "Event type: %s",
        azeventgrid.event_type
    )

    # -----------------------------------------------------
    # Only process BlobCreated
    # -----------------------------------------------------

    if azeventgrid.event_type != (
        "Microsoft.Storage.BlobCreated"
    ):

        logging.info(
            "Ignoring event type: %s",
            azeventgrid.event_type
        )

        return

    event_data = azeventgrid.get_json()

    blob_url = event_data.get(
        "blobUrl"
    )

    if not blob_url:

        logging.error(
            "Blob URL was not found."
        )

        return

    logging.info(
        "Processing blob: %s",
        blob_url
    )

    # -----------------------------------------------------
    # STEP 1 - Read raw JSON
    # -----------------------------------------------------

    try:

        blob_content = get_blob_content(
            blob_url
        )

        news_data = json.loads(
            blob_content
        )

    except Exception as e:

        logging.error(
            "Failed to read/parse blob: %s",
            str(e)
        )

        return

    articles = news_data.get(
        "articles",
        []
    )

    logging.info(
        "Number of articles found: %d",
        len(articles)
    )

    if not articles:
        logging.warning(
            "No articles found."
        )
        return

    # -----------------------------------------------------
    # STEP 2 - Connect to dedup table
    # -----------------------------------------------------

    try:

        table_client = get_dedup_table()

    except Exception as e:

        logging.error(
            "Failed to connect to ArticleDedup: %s",
            str(e)
        )

        return

    # -----------------------------------------------------
    # STEP 3 - Find NEW articles
    # -----------------------------------------------------

    new_articles = []

    duplicate_count = 0
    skipped_count = 0

    for article in articles:

        article_url = article.get(
            "url"
        )

        if not article_url:

            logging.warning(
                "Article has no URL. Skipping."
            )

            skipped_count += 1

            continue

        url_hash = hashlib.sha256(
            article_url.encode("utf-8")
        ).hexdigest()

        try:

            table_client.get_entity(
                partition_key="news",
                row_key=url_hash
            )

            logging.info(
                "DUPLICATE ARTICLE: %s",
                article_url
            )

            duplicate_count += 1

            continue

        except ResourceNotFoundError:

            # New article.
            pass

        except Exception as e:

            logging.error(
                "Dedup check failed: %s",
                str(e)
            )

            continue

        new_articles.append(
            {
                "article": article,
                "url_hash": url_hash
            }
        )

    logging.info(
        "New articles requiring NLP: %d",
        len(new_articles)
    )

    # -----------------------------------------------------
    # Nothing new
    # -----------------------------------------------------

    if not new_articles:

        logging.info(
            "No new articles. NLP processing skipped."
        )

        return

    # -----------------------------------------------------
    # STEP 4 - Language enrichment
    # -----------------------------------------------------

    new_article_objects = [
        item["article"]
        for item in new_articles
    ]

    try:

        language_results = (
            enrich_with_language(
                new_article_objects
            )
        )

    except Exception as e:

        logging.error(
            "Language enrichment failed: %s",
            str(e)
        )

        return

    # -----------------------------------------------------
    # STEP 5 - Generate embeddings
    # -----------------------------------------------------

    try:

        embedding_results = (
            generate_embeddings(
                new_article_objects
            )
        )

    except Exception as e:

        logging.error(
            "Embedding processing failed: %s",
            str(e)
        )

        return

    # -----------------------------------------------------
    # STEP 6 - Merge results
    # -----------------------------------------------------

    enriched_articles = []

    for index, item in enumerate(
        new_articles
    ):

        article = item["article"]

        language_result = (
            language_results.get(
                index,
                {}
            )
        )

        embedding = (
            embedding_results.get(
                index,
                []
            )
        )

        enriched_article = {

            "url": article.get(
                "url",
                ""
            ),

            "title": article.get(
                "title",
                ""
            ),

            "description": article.get(
                "description",
                ""
            ),

            "publishedAt": article.get(
                "publishedAt",
                ""
            ),

            "source": (
                article.get("source") or {}
            ).get(
                "name",
                ""
            ),

            "author": article.get(
                "author",
                ""
            ),

            "sentiment": language_result.get(
                "sentiment",
                ""
            ),

            "entities": language_result.get(
                "entities",
                []
            ),

            "keyPhrases": language_result.get(
                "key_phrases",
                []
            ),

            "embedding": embedding,

            "processedAt": datetime.now(
                timezone.utc
            ).isoformat()
        }

        enriched_articles.append(
            enriched_article
        )

    # -----------------------------------------------------
    # STEP 7 - Write silver data
    # -----------------------------------------------------

    try:

        write_silver_data(
            blob_url,
            enriched_articles
        )

    except Exception as e:

        logging.error(
            "Failed to write silver data: %s",
            str(e)
        )

        return

    # -----------------------------------------------------
    # STEP 8 - Store dedup records
    # -----------------------------------------------------

    stored_count = 0

    for item in new_articles:

        article = item["article"]
        url_hash = item["url_hash"]

        entity = {

            "PartitionKey": "news",

            "RowKey": url_hash,

            "ArticleUrl": article.get(
                "url",
                ""
            ),

            "Title": article.get(
                "title",
                ""
            ),

            "PublishedAt": article.get(
                "publishedAt",
                ""
            ),

            "SourceName": (
                article.get("source") or {}
            ).get(
                "name",
                ""
            ),

            "BlobUrl": blob_url,

            "ProcessedAt": datetime.now(
                timezone.utc
            ).isoformat()
        }

        try:

            table_client.create_entity(
                entity=entity
            )

            stored_count += 1

            logging.info(
                "NEW ARTICLE STORED: %s",
                article.get("url", "")
            )

        except Exception as e:

            logging.error(
                "Failed to store dedup record: %s",
                str(e)
            )

    # -----------------------------------------------------
    # FINAL SUMMARY
    # -----------------------------------------------------

    logging.info(
        "========================================"
    )

    logging.info(
        "LAYER 2 NLP PROCESSING COMPLETE"
    )

    logging.info(
        "Total articles: %d",
        len(articles)
    )

    logging.info(
        "New articles: %d",
        len(new_articles)
    )

    logging.info(
        "Duplicate articles: %d",
        duplicate_count
    )

    logging.info(
        "Skipped articles: %d",
        skipped_count
    )

    logging.info(
        "Dedup records stored: %d",
        stored_count
    )

    logging.info(
        "Silver records written: %d",
        len(enriched_articles)
    )

    logging.info(
        "========================================"
    )
