"""Інструменти доступу до бази знань JarLight (Obsidian + ChromaDB) для ЛР 4."""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path

from .chunker import MarkdownChunker
from .embedder import KnowledgeEmbedder
from .store import KnowledgeStore
from .vault import ObsidianVault


class HashEmbedder:
    """Швидкий локальний лексичний ембедер для офлайн-тестів і демо-режиму."""

    def __init__(self, dim: int = 128):
        self.dim = dim

    def embed(self, texts: list[str], task_type: str = "retrieval_document") -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            tokens = [t.strip(".,:;!?()[]{}\"'").lower() for t in text.split() if t.strip()]
            for tok in tokens or [text.lower()]:
                h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest()[:8], 16)
                vec[h % self.dim] += 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            vectors.append([x / norm for x in vec])
        return vectors


def index_vault(vault_path: Path, store: KnowledgeStore, embedder) -> int:
    """Повна індексація тестового сховища у тимчасову ChromaDB."""
    vault = ObsidianVault(vault_path)
    chunker = MarkdownChunker()
    total = 0
    for note_path in vault.list_notes():
        rel = str(note_path.relative_to(vault_path)).replace("\\", "/")
        note = vault.read_note(rel)
        chunks = chunker.chunk_note(note)
        if not chunks:
            continue
        embs = embedder.embed([c.text for c in chunks], task_type="retrieval_document")
        store.add_chunks(chunks, embs)
        total += len(chunks)
    return total


class KnowledgeTools:
    """Обгортка інструментів БЗ для агента чату та вузла retrieve_context МАС."""

    def __init__(
        self,
        store: KnowledgeStore,
        vault: Path,
        embedder,
        top_k: int = 4,
        max_distance: float = 0.35,
    ):
        self.store = store
        self.vault = Path(vault).resolve()
        self._obsidian = ObsidianVault(self.vault)
        self.embedder = embedder
        self.top_k = top_k
        self.max_distance = max_distance

    def search_knowledge(
        self, query: str, tag: str | None = None, skip_inbox: bool = False
    ) -> str:
        """Семантичний пошук фрагментів у ChromaDB з тегами source та path."""
        q_vec = self.embedder.embed([query], task_type="retrieval_query")[0]
        rows = self.store.query(q_vec, n_results=self.top_k + 2, tag_filter=tag or None)
        blocks: list[str] = []
        for r in rows:
            meta = r["metadata"]
            rel = meta.get("rel_path", "")
            if skip_inbox and rel.startswith("Inbox/"):
                continue
            if r["distance"] <= self.max_distance:
                ref = meta.get("reference", "[[JarLight]]")
                blocks.append(
                    f'<fragment source="{ref}" path="{rel}" distance="{r["distance"]:.3f}">\n'
                    f"{r['text'].strip()}\n</fragment>"
                )
            if len(blocks) >= self.top_k:
                break
        return "\n\n".join(blocks) if blocks else "NOT_FOUND: релевантних фрагментів не знайдено."

    def read_note(self, path: str) -> str:
        """Читає повну нотатку зі сховища з перевіркою path traversal."""
        note = self._obsidian.read_note(path)
        return (
            f'<note path="{note.rel_path}" title="{note.title}">\n'
            f"{note.content.strip()}\n</note>"
        )


def build_tools() -> KnowledgeTools:
    """Збирає реальний клієнт KnowledgeTools за налаштуваннями .env."""
    vault_raw = (os.getenv("OBSIDIAN_VAULT") or os.getenv("KB_VAULT_PATH") or "").strip()
    chroma_raw = (os.getenv("CHROMA_PERSIST_DIR") or "").strip()
    if not vault_raw or not chroma_raw:
        raise RuntimeError("Не вказано KB_VAULT_PATH / OBSIDIAN_VAULT або CHROMA_PERSIST_DIR")
    vault = Path(vault_raw)
    chroma_dir = Path(chroma_raw)
    if not vault.exists() or not chroma_dir.exists():
        raise RuntimeError("Сховище Obsidian або каталог ChromaDB не знайдено")
    collection = os.getenv("CHROMA_COLLECTION", "jarlight_kb")
    embed_model = os.getenv("EMBED_MODEL", "gemini-embedding-001")
    max_dist = float(os.getenv("KB_MAX_DISTANCE", "0.35"))
    store = KnowledgeStore(collection_name=collection, persist_dir=chroma_dir)
    embedder = KnowledgeEmbedder(model_name=embed_model, api_key=os.getenv("GEMINI_API_KEY"))
    return KnowledgeTools(store=store, vault=vault, embedder=embedder, max_distance=max_dist)
