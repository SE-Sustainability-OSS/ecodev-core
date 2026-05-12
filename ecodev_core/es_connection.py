"""
Module implementing a connection to an elastic search instance, and basic insertion/retrieval.
"""
from typing import Any
from typing import Union

import progressbar
from elasticsearch import Elasticsearch
from elasticsearch import helpers

from ecodev_core.logger import logger_get
from ecodev_core.settings import SETTINGS

ES_CLIENT: Union[Elasticsearch, None] = None
log = logger_get(__name__)
ES_BATCH_SIZE = 5000


def get_es_client():
    """
    Get the elasticsearch client
    """
    global ES_CLIENT

    host = SETTINGS.elastic_search.host
    port = SETTINGS.elastic_search.port
    user = SETTINGS.elastic_search.user
    password = SETTINGS.elastic_search.password
    if ES_CLIENT is None:
        ES_CLIENT = Elasticsearch(f'http://{host}:{port}/', basic_auth=[user, password])

    return ES_CLIENT


def create_es_index(body: dict, index: str | None = None) -> None:
    """
    create an es index
    """
    client = get_es_client()
    index = index or SETTINGS.elastic_search.index
    try:
        client.indices.delete(index=index)
    except Exception:
        pass
    client.indices.create(index=index, body=body)
    log.info(f'index {index} created')


def insert_es_fields(operations: list[dict],
                     batch_size: int = ES_BATCH_SIZE,
                     index: str | None = None
                     ) -> None:
    """
    Generic es insertion
    """
    client = get_es_client()
    index = index or SETTINGS.elastic_search.index
    batches = [list(operations)[i:i + batch_size] for i in range(0, len(operations), batch_size)]
    log.info('indexing fields')
    for batch in progressbar.progressbar(batches, redirect_stdout=False):
        helpers.bulk(client, batch, index=index)


def retrieve_es_fields(body: dict[str, Any],
                       index: str | None = None,
                       size: int | None = None
                       ) -> list[dict]:
    """
    Core call to the elasticsearch index
    """
    return get_es_client().search(index=index, body=body, size=size)


def retrieve_es_fields_with_scroll(body: dict, 
                                   index: str,
                                   page_size: int = 1000,
                                   scroll_ttl: str = '1m'
                                   ) -> list[dict]:
    """
    Retrieve all hits for the given query using the scroll API.
    Use this instead of retrieve_es_fields for ES indices with more than 10,000 entries,
    as Elasticsearch's default max_result_window prevents returning more results in a single query.

    Args:
        body: the ES query body (e.g. {"query": {"match_all": {}}})
        index: the ES index to search against
        page_size: number of hits fetched per scroll page (defaults to 1,000)
        scroll_ttl: how long ES keeps the scroll context alive between two consecutive scroll calls
                    (defaults to 1 minute)
    """
    es = get_es_client()
    body = {**body, 'size': page_size}
    response = es.search(index=index, body=body, scroll=scroll_ttl)
    scroll_id = response.get('_scroll_id')
    hits = list(response['hits']['hits'])
    while len(response['hits']['hits']) == page_size:
        response = es.scroll(scroll_id=scroll_id, scroll=scroll_ttl)
        scroll_id = response.get('_scroll_id')
        hits.extend(response['hits']['hits'])
    if scroll_id:
        try:
            es.clear_scroll(scroll_id=scroll_id)
        except Exception:
            pass
    return hits
