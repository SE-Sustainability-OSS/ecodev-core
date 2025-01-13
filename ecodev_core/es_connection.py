"""
Module implementing a connection to an elastic search instance, and basic insertion/retrieval.
"""
from typing import Any
from typing import Union

import progressbar
from elasticsearch import Elasticsearch
from elasticsearch import helpers
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from ecodev_core.logger import logger_get

ES_CLIENT: Union[Elasticsearch, None] = None
log = logger_get(__name__)
ES_BATCH_SIZE = 5000


class ESAuth(BaseSettings):
    """
    Simple ES authentication configuration class
    """
    host: str
    user: str
    password: str
    port: int
    index: str
    model_config = SettingsConfigDict(env_file='.env', env_prefix='ES_')


ES_AUTH = ESAuth()  # type: ignore


def get_es_client():
    """
    Get the elasticsearch client
    """
    global ES_CLIENT

    if ES_CLIENT is None:
        ES_CLIENT = Elasticsearch(f'http://{ES_AUTH.host}:{ES_AUTH.port}/',
                                  basic_auth=[ES_AUTH.user, ES_AUTH.password])

    return ES_CLIENT


def create_es_index(body: dict) -> None:
    """
    create an es index
    """
    client = get_es_client()
    try:
        client.indices.delete(index=ES_AUTH.index)
    except Exception:
        pass
    client.indices.create(index=ES_AUTH.index, body=body)
    log.info(f'index {ES_AUTH.index} created')


def insert_es_fields(operations: list[dict], batch_size: int = ES_BATCH_SIZE) -> None:
    """
    Generic es insertion
    """
    client = get_es_client()
    batches = [list(operations)[i:i + batch_size] for i in range(0, len(operations), batch_size)]
    log.info('indexing fields')
    for batch in progressbar.progressbar(batches, redirect_stdout=False):
        helpers.bulk(client, batch, index=ES_AUTH.index)


def retrieve_es_fields(body: dict[str, Any]) -> list[dict]:
    """
    Core call to the elasticsearch index
    """
    return get_es_client().search(index=ES_AUTH.index, body=body)
