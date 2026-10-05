import os
import json
import hashlib

from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential


# Load environment variables
load_dotenv()

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")

STORAGE_CONNECTION = os.getenv("NEWS_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("NEWS_CONTAINER")
SILVER_PREFIX = os.getenv("SILVER_PREFIX")


# Validate required settings
required_values = {
    "AZURE_SEARCH_ENDPOINT": SEARCH_ENDPOINT,
    "AZURE_SEARCH_ADMIN_KEY": SEARCH_KEY,
    "AZURE_SEARCH_INDEX_NAME": INDEX_NAME,
    "NEWS_STORAGE_CONNECTION_STRING": STORAGE_CONNECTION,
    "NEWS_CONTAINER": CONTAINER_NAME,
    "SILVER_PREFIX": SILVER_PREFIX,
}

missing = [
    name for name, value in required_values.items()
    if not value
]

if missing:
    raise ValueError(
        "Missing environment variables: "
        + ", ".join(missing)
    )


# ---------------------------------------------------------
# Connect to Azure AI Search
# ---------------------------------------------------------

search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=INDEX_NAME,
    credential=AzureKeyCredential(SEARCH_KEY)
)


# ---------------------------------------------------------
# Connect to Azure Blob Storage
# ---------------------------------------------------------

blob_service = BlobServiceClient.from_connection_string(
    STORAGE_CONNECTION
)

container_client = blob_service.get_container_client(
    CONTAINER_NAME
)


# ---------------------------------------------------------
# Read Silver JSON files
# ---------------------------------------------------------

documents = []

print("Reading Silver articles...")
print(f"Container: {CONTAINER_NAME}")
print(f"Prefix: {SILVER_PREFIX}")
print()


for blob in container_client.list_blobs(
    name_starts_with=SILVER_PREFIX
):

    # Only process JSON files
    if not blob.name.endswith(".json"):
        continue

    print(f"Reading: {blob.name}")

    blob_client = container_client.get_blob_client(
        blob.name
    )

    content = blob_client.download_blob().readall()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        print(f"Skipping invalid JSON: {blob.name}")
        continue


    # -----------------------------------------------------
    # Support both:
    #
    # {"articles": [...]}
    #
    # and:
    #
    # {...single article...}
    # -----------------------------------------------------

    if isinstance(data, dict) and "articles" in data:
        articles = data["articles"]
    else:
        articles = [data]


    # -----------------------------------------------------
    # Prepare Search documents
    # -----------------------------------------------------

    for article in articles:

        url = article.get("url")

        # URL is required because it is our stable source
        # for generating the Search document ID.
        if not url:
            print("Skipping article without URL")
            continue


        # Azure AI Search keys cannot contain characters
        # such as /, :, ?, etc.
        #
        # Therefore create a safe deterministic ID from
        # the article URL.
        document_id = hashlib.sha256(
            url.encode("utf-8")
        ).hexdigest()


        document = {
            "id": document_id,

            "url": url,

            "title": article.get("title"),

            "description": article.get("description"),

            "publishedAt": article.get("publishedAt"),

            "source": article.get("source"),

            "author": article.get("author"),

            "sentiment": article.get("sentiment"),

            "entities": article.get(
                "entities",
                []
            ),

            "keyPhrases": article.get(
                "keyPhrases",
                []
            ),

            "embedding": article.get(
                "embedding",
                []
            )
        }


        # Skip documents without embeddings
        # because the Search index expects the
        # vector field.
        if not document["embedding"]:
            print(
                f"Skipping article without embedding: "
                f"{url}"
            )
            continue


        documents.append(document)


print()
print(
    f"Documents prepared for indexing: "
    f"{len(documents)}"
)
print()


# ---------------------------------------------------------
# Upload documents to Azure AI Search
# ---------------------------------------------------------

batch_size = 100

total_uploaded = 0

for i in range(
    0,
    len(documents),
    batch_size
):

    batch = documents[
        i:i + batch_size
    ]

    print(
        f"Uploading batch "
        f"{(i // batch_size) + 1} "
        f"({len(batch)} documents)..."
    )


    try:

        results = search_client.upload_documents(
            documents=batch
        )


        succeeded = sum(
            1
            for result in results
            if result.succeeded
        )

        failed = len(batch) - succeeded

        total_uploaded += succeeded


        print(
            f"Successful: {succeeded} | "
            f"Failed: {failed}"
        )


        # Print individual failures
        for result in results:

            if not result.succeeded:

                print(
                    f"FAILED document: "
                    f"{result.key}"
                )

                print(
                    f"Error: "
                    f"{result.error_message}"
                )


    except Exception as error:

        print(
            f"Batch upload failed: "
            f"{error}"
        )


print()
print("=" * 50)
print("SEARCH INDEXING COMPLETED")
print("=" * 50)
print(
    f"Total documents uploaded: "
    f"{total_uploaded}"
)
print("=" * 50)