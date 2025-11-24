"""
Embedding factory helpers (Jina).
"""
from typing import Any, List, Optional, Sequence, Tuple

import requests
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.embeddings.jinaai import JinaEmbedding

from ai_parts.config import Settings, get_settings


class JinaImageEmbedding(BaseEmbedding):
    """Direct HTTP wrapper for Jina multi-modal embeddings."""

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__()
        object.__setattr__(self, "model_name", model)
        object.__setattr__(self, "_api_key", api_key)
        object.__setattr__(self, "_url", "https://api.jina.ai/v1/embeddings")

    @classmethod
    def from_settings(cls, settings: Settings) -> "JinaImageEmbedding":
        return cls(api_key=settings.jina_api_key, model=settings.jina_image_model)

    def _http_embed(self, images: Sequence[str]) -> List[List[float]]:
        payload = {
            "model": self.model_name,
            "input": list(images),
        }
        resp = requests.post(
            self._url,
            json=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=60,
        )
        if not resp.ok:
            raise RuntimeError(f"Jina image embed failed: {resp.status_code} {resp.text}")
        data = resp.json().get("data", [])
        return [item["embedding"] for item in data]

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._http_embed([text])[0]

    def _get_text_embedding_batch(self, texts: Sequence[str]) -> List[List[float]]:
        return self._http_embed(texts)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._http_embed([query])[0]

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._http_embed([query])[0]

    def get_image_embedding(self, image: Any) -> List[float]:
        return self._http_embed([image])[0]

    def get_image_embedding_batch(self, images: Sequence[Any]) -> List[List[float]]:
        return self._http_embed(images)


def get_jina_embeddings(settings: Optional[Settings] = None) -> Tuple[Optional[BaseEmbedding], Optional[BaseEmbedding]]:
    cfg = settings or get_settings()
    if not cfg.jina_api_key:
        return None, None

    text_embed = JinaEmbedding(
        api_key=cfg.jina_api_key,
        model=cfg.jina_text_model,
    )
    # Fix: JinaEmbedding uses 'model' internally, but 'model_name' defaults to 'unknown'
    # Override model_name to match the actual model
    object.__setattr__(text_embed, "model_name", cfg.jina_text_model)

    image_embed = JinaImageEmbedding.from_settings(cfg)
    return text_embed, image_embed
