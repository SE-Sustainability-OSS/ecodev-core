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
from ecodev_core.settings import SETTINGS

ES_CLIENT: Union[Elasticsearch, None] = None
log = logger_get(__name__)
ES_BATCH_SIZE = 5000


class ESAuth(BaseSettings):
    """
    Simple ES authentication configuration class
    """
    host: str = ''
    user: str = ''
    password: str = ''
    port: int = 9200
    index: str = ''
    model_config = SettingsConfigDict(env_file='.env', env_prefix='ES_')


ES_AUTH, ES_SETTINGS = ESAuth(), SETTINGS.elastic_search  # type: ignore[attr-defined]
_HOST, _PORT = ES_SETTINGS.host or ES_AUTH.host,  ES_SETTINGS.port or ES_AUTH.port
_USER, _PASSWD = ES_SETTINGS.user or ES_AUTH.user, ES_SETTINGS.password or ES_AUTH.password
_INDEX = ES_SETTINGS.index or ES_AUTH.index


def get_es_client():
    """
    Get the elasticsearch client
    """
    global ES_CLIENT

    if ES_CLIENT is None:
        ES_CLIENT = Elasticsearch(f'http://{_HOST}:{_PORT}/', basic_auth=[_USER, _PASSWD])

    return ES_CLIENT


def create_es_index(body: dict, index: str | None = None) -> None:
    """
    create an es index
    """
    client = get_es_client()
    index = index or _INDEX
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
    index = index or _INDEX
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
