import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    openai_endpoint: str
    openai_api_key: str
    openai_api_version: str
    chat_deployment: str
    embedding_deployment: str
    search_endpoint: str
    search_api_key: str
    search_index_fixed: str
    search_index_semantic: str


def get_settings() -> Settings:
    return Settings(
        openai_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
        openai_api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        chat_deployment=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
        embedding_deployment=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
        search_endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        search_api_key=os.environ["AZURE_SEARCH_API_KEY"],
        search_index_fixed=os.environ["AZURE_SEARCH_INDEX_FIXED"],
        search_index_semantic=os.environ["AZURE_SEARCH_INDEX_SEMANTIC"],
    )
