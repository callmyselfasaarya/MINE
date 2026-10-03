import json
import math
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from jarvis.config import DATA_DIR

logger = logging.getLogger(__name__)

SEMANTIC_FILE = DATA_DIR / "semantic_memory.json"

def _tokenize(text: str) -> List[str]:
    """Extract lowercased alphanumeric words."""
    return re.findall(r"\b\w{2,}\b", text.lower())

class SemanticMemory:
    """
    Semantic Memory subsystem:
    - Indexes text items with metadata and timestamp
    - Hybrid TF-IDF / BM25 term-frequency vector similarity search
    - Enables semantic recall of documents, previous assistant discussions, and knowledge
    """

    def __init__(self, index_file: Optional[Path] = None):
        self.index_file = index_file or SEMANTIC_FILE
        self.documents: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if not self.index_file.exists():
            self.documents = []
            return
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                self.documents = json.load(f)
        except Exception as e:
            logger.error(f"Error loading semantic memory: {e}")
            self.documents = []

    def _save(self):
        try:
            self.index_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(self.documents, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving semantic memory: {e}")

    def add_entry(self, content: str, source: str = "user", metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add a passage to semantic memory."""
        doc_id = f"sem_{len(self.documents) + 1}_{int(datetime.now().timestamp())}"
        entry = {
            "id": doc_id,
            "content": content.strip(),
            "source": source,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        self.documents.append(entry)
        self._save()
        return doc_id

    def search(self, query: str, top_k: int = 5, score_threshold: float = 0.05) -> List[Dict[str, Any]]:
        """
        Search for semantically relevant passages using TF-IDF / BM25-style scoring.
        """
        if not self.documents or not query.strip():
            return []

        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        # Calculate document frequencies
        n_docs = len(self.documents)
        df: Dict[str, int] = {}
        doc_tokens_list = []

        for doc in self.documents:
            tokens = _tokenize(doc["content"])
            doc_tokens_list.append(tokens)
            unique_tokens = set(tokens)
            for t in unique_tokens:
                df[t] = df.get(t, 0) + 1

        # Calculate scores
        avg_doc_len = sum(len(t) for t in doc_tokens_list) / max(1, n_docs)
        k1 = 1.2
        b = 0.75

        scored: List[Dict[str, Any]] = []

        for idx, doc in enumerate(self.documents):
            tokens = doc_tokens_list[idx]
            doc_len = len(tokens)
            if doc_len == 0:
                continue

            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1

            score = 0.0
            for qt in q_tokens:
                if qt in tf:
                    doc_freq = df.get(qt, 1)
                    idf = math.log((n_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
                    term_tf = tf[qt]
                    denom = term_tf + k1 * (1 - b + b * (doc_len / max(1.0, avg_doc_len)))
                    score += idf * ((term_tf * (k1 + 1)) / max(1e-6, denom))

            if score >= score_threshold:
                scored.append({
                    **doc,
                    "score": round(score, 4)
                })

        # Sort descending by score
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def clear(self):
        self.documents = []
        self._save()

    def count(self) -> int:
        return len(self.documents)
