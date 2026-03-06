"""Dynamic tool filtering via semantic embedding.

Embeds all tool descriptions at startup, retrieves top-k per query
via cosine similarity. Reduces context window from all tools to 3-7.

References:
  - arXiv:2411.15399 (Less is More)
  - Redis Engineering Blog Dec 2025 (98% token reduction)
  - Jenova AI Sep 2025 (5-7 tools = 92% accuracy)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Default model — small, fast, good for short descriptions
DEFAULT_MODEL = "all-MiniLM-L6-v2"
DEFAULT_TOP_K = 5
CATALOG_PATH = Path(__file__).parent.parent.parent / "data" / "tool_catalog.json"


class ToolFilter:
    """Semantic tool retrieval via embedding similarity."""

    def __init__(
        self,
        catalog_path: str | Path = CATALOG_PATH,
        model_name: str = DEFAULT_MODEL,
        top_k: int = DEFAULT_TOP_K,
    ):
        self.top_k = top_k
        self.model_name = model_name
        self._model = None
        self._tools: list[dict[str, Any]] = []
        self._embeddings: np.ndarray | None = None
        self._load_catalog(catalog_path)

    def _load_catalog(self, path: str | Path) -> None:
        path = Path(path)
        if not path.exists():
            logger.warning("Tool catalog not found at %s", path)
            return
        with open(path) as f:
            self._tools = json.load(f)
        logger.info("Loaded %d tool descriptions", len(self._tools))

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            logger.info("Loaded embedding model: %s", self.model_name)
        return self._model

    def build_index(self) -> None:
        """Embed all tool descriptions. Call once at startup."""
        if not self._tools:
            raise ValueError("No tools loaded — check catalog path")
        texts = [
            f"{t['name']}: {t['description']}" for t in self._tools
        ]
        self._embeddings = self.model.encode(texts, normalize_embeddings=True)
        logger.info("Built embedding index: %d tools, dim=%d",
                     len(self._tools), self._embeddings.shape[1])

    def save_index(self, path: str | Path) -> None:
        """Save precomputed embeddings to disk."""
        if self._embeddings is None:
            raise ValueError("No index built — call build_index() first")
        path = Path(path)
        np.save(path, self._embeddings)
        logger.info("Saved index to %s", path)

    def load_index(self, path: str | Path) -> None:
        """Load precomputed embeddings from disk."""
        path = Path(path)
        self._embeddings = np.load(path)
        logger.info("Loaded index from %s: %d tools", path, self._embeddings.shape[0])

    def query(self, user_input: str, top_k: int | None = None) -> list[dict[str, Any]]:
        """Retrieve top-k tools most relevant to user input.

        Returns list of {name, description, score} dicts, sorted by relevance.
        """
        if self._embeddings is None:
            self.build_index()

        k = top_k or self.top_k
        q_emb = self.model.encode([user_input], normalize_embeddings=True)
        scores = (self._embeddings @ q_emb.T).flatten()
        top_indices = np.argsort(scores)[::-1][:k]

        results = []
        for idx in top_indices:
            t = self._tools[idx]
            results.append({
                "name": t["name"],
                "description": t["description"],
                "full_doc": t.get("full_doc", ""),
                "score": float(scores[idx]),
            })
        return results

    def filter_tools(self, user_input: str, all_tools: list[dict], top_k: int | None = None) -> list[dict]:
        """Given a user query and a list of MCP tool dicts, return only the top-k relevant ones.

        Args:
            user_input: The operator's query/intent.
            all_tools: Full list of tool definition dicts (must have 'name' key).
            top_k: Override default top_k.

        Returns:
            Filtered list of tool dicts.
        """
        relevant = self.query(user_input, top_k=top_k)
        relevant_names = {r["name"] for r in relevant}
        return [t for t in all_tools if t["name"] in relevant_names]

    def tool_names(self) -> list[str]:
        """Return all tool names in the catalog."""
        return [t["name"] for t in self._tools]

    def stats(self) -> dict[str, Any]:
        """Return index statistics."""
        return {
            "total_tools": len(self._tools),
            "index_built": self._embeddings is not None,
            "embedding_dim": self._embeddings.shape[1] if self._embeddings is not None else None,
            "model": self.model_name,
            "default_top_k": self.top_k,
        }


# --- Singleton for server use ---
_instance: ToolFilter | None = None


def get_filter(
    catalog_path: str | Path = CATALOG_PATH,
    model_name: str = DEFAULT_MODEL,
    top_k: int = DEFAULT_TOP_K,
) -> ToolFilter:
    """Get or create the singleton ToolFilter."""
    global _instance
    if _instance is None:
        _instance = ToolFilter(catalog_path=catalog_path, model_name=model_name, top_k=top_k)
        index_path = Path(catalog_path).parent / "tool_embeddings.npy"
        if index_path.exists():
            _instance.load_index(index_path)
        else:
            _instance.build_index()
            _instance.save_index(index_path)
    return _instance
