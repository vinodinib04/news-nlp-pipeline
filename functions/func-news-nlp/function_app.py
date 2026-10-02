import logging
import hashlib
import json
import os
from datetime import datetime, timezone

import azure.functions as func
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient


app = func.FunctionApp()


def get_storage_connection_string():
    """
    Get the connection string for the newsstorage1 storage account.
    """
    connection_string = os.environ.get(
        "NEWS_STORAGE_CONNECTION_STRING"
    )

    if not connection_string:
        raise RuntimeError(
            "NEWS_STORAGE_CONNECTION_STRING is not configured."
        )

    return connection_string


def get_dedup_table():
    """
    Connect to the ArticleDedup Azure Table.
    """
    connection_string = get_storage_connection_string()

    table_service = TableServiceClient.from_connection_string(
        connection_string
    )

    table_client = table_service.get_table_client(
        table_name="ArticleDedup"
    )

    return table_client


def get_blob_content(blob_url):
    """
    Download the NewsAPI JSON blob from newsstorage1.
    """

    connection_string = get_storage_connection_string()

    blob_service = BlobServiceClient.from_connection_string(
        connection_string
    )

    # Example:
    # https://newsstorage1.blob.core.windows.net/news/raw/file.json
    #
    # Everything after .blob.core.windows.net/ is:
    # news/raw/file.json

    marker = ".blob.core.windows.net/"

    if marker not in blob_url:
        raise ValueError(
            f"Unexpected blob URL: {blob_url}"
        )

    container_and_blob = blob_url.split(
        marker,
        1
    )[1]

    # First part = container
    # Remaining part = blob path
    parts = container_and_blob.split("/", 1)

    if len(parts) != 2:
        raise ValueError(
            f"Could not determine container/blob from URL: {blob_url}"
        )

    container_name = parts[0]
    blob_name = parts[1]

    logging.info(
        "Storage account container: %s",
        container_name
    )

    logging.info(
        "Storage blob: %s",
        blob_name
    )

    blob_client = blob_service.get_blob_client(
        container=container_name,
        blob=blob_name
    )

    download_stream = blob_client.download_blob()

    return download_stream.readall()


@app.event_grid_trigger(arg_name="azeventgrid")
def processnewsnlp(azeventgrid: func.EventGridEvent):

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

    # Only process BlobCreated events.
    if azeventgrid.event_type != "Microsoft.Storage.BlobCreated":

        logging.info(
            "Ignoring event type: %s",
            azeventgrid.event_type
        )

        return

    event_data = azeventgrid.get_json()

    logging.info(
        "Event data: %s",
        event_data
    )

    blob_url = event_data.get("blobUrl")

    if not blob_url:

        logging.error(
            "Blob URL was not found in Event Grid event."
        )

        return

    logging.info(
        "Reading blob: %s",
        blob_url
    )

    # ---------------------------------------------------------
    # STEP 1: Read the NewsAPI JSON file
    # ---------------------------------------------------------

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

    # NewsAPI structure:
    #
    # {
    #     "status": "ok",
    #     "totalResults": ...,
    #     "articles": [...]
    # }

    articles = news_data.get(
        "articles",
        []
    )

    logging.info(
        "Number of articles found: %d",
        len(articles)
    )

    # ---------------------------------------------------------
    # STEP 2: Connect to ArticleDedup table
    # ---------------------------------------------------------

    try:

        table_client = get_dedup_table()

    except Exception as e:

        logging.error(
            "Failed to connect to ArticleDedup table: %s",
            str(e)
        )

        return

    new_articles = 0
    duplicate_articles = 0
    skipped_articles = 0

    # ---------------------------------------------------------
    # STEP 3: Process every NewsAPI article
    # ---------------------------------------------------------

    for article in articles:

        article_url = article.get(
            "url"
        )

        # Some articles may not have a URL.
        if not article_url:

            logging.warning(
                "Article has no URL. Skipping."
            )

            skipped_articles += 1

            continue

        # -----------------------------------------------------
        # STEP 4: Create SHA-256 hash from article URL
        # -----------------------------------------------------

        url_hash = hashlib.sha256(
            article_url.encode("utf-8")
        ).hexdigest()

        # -----------------------------------------------------
        # STEP 5: Check whether URL already exists
        # -----------------------------------------------------

        try:

            table_client.get_entity(
                partition_key="news",
                row_key=url_hash
            )

            # Entity exists.
            logging.info(
                "DUPLICATE ARTICLE: %s",
                article_url
            )

            duplicate_articles += 1

            continue

        except ResourceNotFoundError:

            # Entity does not exist.
            # Therefore this is a new article.
            pass

        except Exception as e:

            logging.error(
                "Error checking ArticleDedup for %s: %s",
                article_url,
                str(e)
            )

            continue

        # -----------------------------------------------------
        # STEP 6: Store the new article in ArticleDedup
        # -----------------------------------------------------

        entity = {
            "PartitionKey": "news",
            "RowKey": url_hash,
            "ArticleUrl": article_url,
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

            logging.info(
                "NEW ARTICLE: %s",
                article_url
            )

            new_articles += 1

        except Exception as e:

            logging.error(
                "Failed to store dedup record for %s: %s",
                article_url,
                str(e)
            )

    # ---------------------------------------------------------
    # STEP 7: Final summary
    # ---------------------------------------------------------

    logging.info(
        "========================================"
    )

    logging.info(
        "DEDUPLICATION COMPLETE"
    )

    logging.info(
        "Total articles: %d",
        len(articles)
    )

    logging.info(
        "New articles: %d",
        new_articles
    )

    logging.info(
        "Duplicate articles: %d",
        duplicate_articles
    )

    logging.info(
        "Skipped articles: %d",
        skipped_articles
    )

    logging.info(
        "========================================"
    )