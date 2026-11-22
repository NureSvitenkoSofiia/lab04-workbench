"""Модуль генерації векторних ембедингів (Gemini API та локальний fallback)."""

import os
from typing import Literal


class KnowledgeEmbedder:
    """Генератор ембедингів з підтримкою типів задач retrieval_document та retrieval_query."""

    def __init__(self, model_name: str = "gemini-embedding-001", api_key: str | None = None):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._client = None

        if self.api_key:
            try:
                from google import genai

                self._client = genai.Client(api_key=self.api_key)
            except Exception:
                self._client = None

    def embed(
        self,
        texts: list[str],
        task_type: Literal["retrieval_document", "retrieval_query"] = "retrieval_document",
    ) -> list[list[float]]:
        """Генерує векторні представлення для списку текстів."""
        if not texts:
            return []

        if self._client:
            try:
                formatted = [f"[{task_type}] {t}" for t in texts]
                result = self._client.models.embed_content(
                    model=self.model_name,
                    contents=formatted,
                )
                return [e.values for e in result.embeddings]
            except Exception as e:
                print(
                    f"[Embedder Notice] Gemini embedding API failed ({e}), using deterministic fallback."
                )
                return [self._fallback_vector(t) for t in texts]

        return [self._fallback_vector(t) for t in texts]

    def _fallback_vector(self, text: str, dim: int = 768) -> list[float]:
        """Детермінований псевдо-ембединг для тестів без викликів мережі."""
        import hashlib
        import math

        vec = []
        for i in range(dim):
            h = hashlib.sha256(f"{text}_{i}".encode("utf-8")).hexdigest()
            val = (int(h[:8], 16) / 0xFFFFFFFF) * 2 - 1
            vec.append(val)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]
