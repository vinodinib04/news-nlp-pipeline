import os

from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI


# =========================================================
# 1. Load environment variables
# =========================================================

load_dotenv()

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")

OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
EMBEDDING_DEPLOYMENT = os.getenv(
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
)


# =========================================================
# 2. Validate configuration
# =========================================================

required_values = {
    "AZURE_SEARCH_ENDPOINT": SEARCH_ENDPOINT,
    "AZURE_SEARCH_ADMIN_KEY": SEARCH_KEY,
    "AZURE_SEARCH_INDEX_NAME": INDEX_NAME,
    "AZURE_OPENAI_ENDPOINT": OPENAI_ENDPOINT,
    "AZURE_OPENAI_KEY": OPENAI_KEY,
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": EMBEDDING_DEPLOYMENT,
}

missing = [
    name
    for name, value in required_values.items()
    if not value
]

if missing:
    raise ValueError(
        "Missing environment variables: "
        + ", ".join(missing)
    )


# =========================================================
# 3. Connect to Azure AI Search
# =========================================================

search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=INDEX_NAME,
    credential=AzureKeyCredential(SEARCH_KEY)
)


# =========================================================
# 4. Connect to Azure OpenAI
# =========================================================

openai_client = AzureOpenAI(
    azure_endpoint=OPENAI_ENDPOINT,
    api_key=OPENAI_KEY,
    api_version="2024-10-21"
)


# =========================================================
# 5. Define search query
# =========================================================

query = "artificial intelligence and technology"

print()
print("=" * 70)
print("QUERY")
print("=" * 70)
print(query)


# =========================================================
# 6. Generate embedding for the search query
# =========================================================

print()
print("Generating query embedding...")

embedding_response = openai_client.embeddings.create(
    model=EMBEDDING_DEPLOYMENT,
    input=query
)

query_vector = embedding_response.data[0].embedding

print(
    f"Embedding dimensions: {len(query_vector)}"
)


# =========================================================
# 7. Hybrid Search
#
#    BM25 keyword search:
#       search_text=query
#
#    Vector search:
#       vector_queries
#
#    Azure AI Search automatically combines the
#    keyword and vector result lists using RRF.
# =========================================================

print()
print("Running hybrid search...")
print("BM25 + Vector + RRF")


results = search_client.search(
    search_text=query,

    vector_queries=[
        {
            "kind": "vector",
            "vector": query_vector,
            "fields": "embedding",
            "k": 10
        }
    ],

    top=10,

    select=[
        "id",
        "url",
        "title",
        "description",
        "publishedAt",
        "source",
        "sentiment"
    ]
)


# =========================================================
# 8. Display results
# =========================================================

print()
print("=" * 70)
print("HYBRID SEARCH RESULTS")
print("=" * 70)

result_count = 0

for rank, result in enumerate(results, start=1):

    result_count += 1

    print()
    print(f"Rank: {rank}")
    print(
        f"RRF/Search Score: "
        f"{result.get('@search.score')}"
    )
    print(
        f"Title: "
        f"{result.get('title')}"
    )
    print(
        f"Source: "
        f"{result.get('source')}"
    )
    print(
        f"Sentiment: "
        f"{result.get('sentiment')}"
    )
    print(
        f"Published: "
        f"{result.get('publishedAt')}"
    )
    print(
        f"URL: "
        f"{result.get('url')}"
    )


# =========================================================
# 9. Final verification
# =========================================================

print()
print("=" * 70)
print("HYBRID SEARCH VERIFICATION")
print("=" * 70)

print(
    f"Results returned: {result_count}"
)

print(
    "Keyword retrieval: BM25"
)

print(
    "Vector retrieval: HNSW"
)

print(
    "Similarity metric: Cosine"
)

print(
    "Result fusion: Reciprocal Rank Fusion (RRF)"
)

print("=" * 70)
print("HYBRID SEARCH TEST COMPLETED")
print("=" * 70)