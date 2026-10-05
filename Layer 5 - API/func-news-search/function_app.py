import azure.functions as func
import logging
import json
import os

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient


app = func.FunctionApp(
    http_auth_level=func.AuthLevel.ANONYMOUS
)


def get_search_client():
    endpoint = os.environ.get("SEARCH_ENDPOINT")
    api_key = os.environ.get("SEARCH_API_KEY")
    index_name = os.environ.get("SEARCH_INDEX_NAME")

    if not endpoint or not api_key or not index_name:
        raise RuntimeError(
            "Azure AI Search settings are not configured."
        )

    return SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(api_key)
    )


@app.route(
    route="searchnews",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def searchnews(req: func.HttpRequest) -> func.HttpResponse:

    logging.info("Layer 5 search API called.")

    query = req.params.get("q")

    if not query:
        return func.HttpResponse(
            json.dumps({
                "error": "Missing required query parameter: q"
            }),
            status_code=400,
            mimetype="application/json"
        )

    try:
        search_client = get_search_client()

        results = search_client.search(
            search_text=query,
            top=10,
            select=[
                "id",
                "url",
                "title",
                "description",
                "publishedAt",
                "source",
                "author",
                "sentiment",
                "entities",
                "keyPhrases"
            ]
        )

        articles = []

        for result in results:
            articles.append({
                "id": result.get("id"),
                "url": result.get("url"),
                "title": result.get("title"),
                "description": result.get("description"),
                "publishedAt": result.get("publishedAt"),
                "source": result.get("source"),
                "author": result.get("author"),
                "sentiment": result.get("sentiment"),
                "entities": result.get("entities"),
                "keyPhrases": result.get("keyPhrases"),
                "score": result.get("@search.score")
            })

        response = {
            "query": query,
            "count": len(articles),
            "results": articles
        }

        return func.HttpResponse(
            json.dumps(response, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logging.exception("Search API failed.")

        return func.HttpResponse(
            json.dumps({
                "error": "Search failed",
                "details": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )