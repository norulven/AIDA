"""Vector store for semantic memory using sentence-transformers and FAISS."""

import json
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from src.memory.database import MemoryDatabase


@dataclass
class SearchResult:
    """A semantic search result."""

    message_id: int
    session_id: str
    content: str
    score: float
    timestamp: datetime | None


class EmbeddingStore(QObject):
    """Vector store for semantic search using sentence-transformers."""

    embedding_added = Signal(int)
    index_rebuilt = Signal()

    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM = 384

    def __init__(
        self,
        db: "MemoryDatabase",
        data_dir: Path | None = None,
        cache_dir: Path | None = None
    ):
        super().__init__()

        self.db = db

        if data_dir is None:
            data_dir = Path.home() / ".local/share/aida/embeddings"
        if cache_dir is None:
            cache_dir = Path.home() / ".cache/aida/embedding_model"

        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.index_path = self.data_dir / "index.bin"
        self.metadata_path = self.data_dir / "metadata.json"

        self._model = None
        self._index = None
        self._metadata: dict[int, dict] = {}
        self._lock = threading.Lock()

        self._load_metadata()

    def _load_model(self):
        """Lazy load the sentence-transformer model."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.MODEL_NAME,
                cache_folder=str(self.cache_dir)
            )
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for semantic memory. "
                "Install with: pip install sentence-transformers"
            )

    def _load_index(self):
        """Load or create the FAISS index."""
        if self._index is not None:
            return

        try:
            import faiss
        except ImportError:
            raise ImportError(
                "faiss-cpu is required for semantic memory. "
                "Install with: pip install faiss-cpu"
            )

        if self.index_path.exists():
            self._index = faiss.read_index(str(self.index_path))
        else:
            self._index = faiss.IndexFlatIP(self.EMBEDDING_DIM)

    def _load_metadata(self):
        """Load metadata mapping."""
        if self.metadata_path.exists():
            with open(self.metadata_path) as f:
                data = json.load(f)
                self._metadata = {int(k): v for k, v in data.items()}

    def _save_metadata(self):
        """Save metadata mapping."""
        with open(self.metadata_path, "w") as f:
            json.dump(self._metadata, f)

    def _save_index(self):
        """Save FAISS index to disk."""
        if self._index is not None:
            try:
                import faiss
                faiss.write_index(self._index, str(self.index_path))
            except Exception:
                pass

    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for text."""
        self._load_model()
        embedding = self._model.encode(text, normalize_embeddings=True)
        return embedding.astype(np.float32)

    def add_embedding(
        self,
        message_id: int,
        session_id: str,
        content: str,
        timestamp: datetime | None = None
    ) -> int:
        """Add embedding for a message."""
        with self._lock:
            self._load_model()
            self._load_index()

            embedding = self.embed_text(content)
            embedding = embedding.reshape(1, -1)

            embedding_id = self._index.ntotal
            self._index.add(embedding)

            self._metadata[embedding_id] = {
                "message_id": message_id,
                "session_id": session_id,
                "content": content[:500],
                "timestamp": timestamp.isoformat() if timestamp else None
            }

            self._save_metadata()
            self._save_index()

            self.embedding_added.emit(message_id)
            return embedding_id

    def search(
        self,
        query: str,
        k: int = 5,
        min_score: float = 0.3
    ) -> list[SearchResult]:
        """Search for semantically similar messages."""
        with self._lock:
            self._load_model()
            self._load_index()

            if self._index.ntotal == 0:
                return []

            query_embedding = self.embed_text(query)
            query_embedding = query_embedding.reshape(1, -1)

            actual_k = min(k, self._index.ntotal)
            scores, indices = self._index.search(query_embedding, actual_k)

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or score < min_score:
                    continue

                if idx not in self._metadata:
                    continue

                meta = self._metadata[idx]
                timestamp = None
                if meta.get("timestamp"):
                    try:
                        timestamp = datetime.fromisoformat(meta["timestamp"])
                    except (ValueError, TypeError):
                        pass

                results.append(SearchResult(
                    message_id=meta["message_id"],
                    session_id=meta["session_id"],
                    content=meta["content"],
                    score=float(score),
                    timestamp=timestamp
                ))

            return results

    def search_in_session(
        self,
        query: str,
        session_id: str,
        k: int = 5,
        min_score: float = 0.3
    ) -> list[SearchResult]:
        """Search within a specific session."""
        all_results = self.search(query, k=k * 3, min_score=min_score)

        session_results = [
            r for r in all_results
            if r.session_id == session_id
        ]

        return session_results[:k]

    def delete_embeddings(self, message_ids: list[int]) -> None:
        """Remove embeddings for deleted messages.

        Note: FAISS IndexFlatIP doesn't support deletion,
        so we just remove from metadata. The orphaned vectors
        will be cleaned up on next rebuild.
        """
        with self._lock:
            ids_to_remove = []
            for embedding_id, meta in self._metadata.items():
                if meta["message_id"] in message_ids:
                    ids_to_remove.append(embedding_id)

            for embedding_id in ids_to_remove:
                del self._metadata[embedding_id]

            self._save_metadata()

    def rebuild_index(self) -> None:
        """Rebuild the entire index from database."""
        with self._lock:
            try:
                import faiss
            except ImportError:
                return

            self._load_model()

            rows = self.db.fetchall(
                """SELECT m.id, m.session_id, m.content, m.timestamp
                   FROM messages m
                   WHERE m.role IN ('user', 'assistant')
                   ORDER BY m.timestamp ASC"""
            )

            if not rows:
                self._index = faiss.IndexFlatIP(self.EMBEDDING_DIM)
                self._metadata = {}
                self._save_index()
                self._save_metadata()
                return

            self._index = faiss.IndexFlatIP(self.EMBEDDING_DIM)
            self._metadata = {}

            batch_size = 32
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                texts = [row["content"] for row in batch]
                embeddings = self._model.encode(texts, normalize_embeddings=True)
                embeddings = embeddings.astype(np.float32)

                for j, row in enumerate(batch):
                    embedding_id = self._index.ntotal
                    self._index.add(embeddings[j:j+1])

                    timestamp = row["timestamp"]
                    self._metadata[embedding_id] = {
                        "message_id": row["id"],
                        "session_id": row["session_id"],
                        "content": row["content"][:500],
                        "timestamp": timestamp.isoformat() if timestamp else None
                    }

            self._save_index()
            self._save_metadata()
            self.index_rebuilt.emit()

    def get_embedding_count(self) -> int:
        """Get total number of embeddings."""
        return len(self._metadata)

    def is_available(self) -> bool:
        """Check if embedding dependencies are available."""
        try:
            import sentence_transformers  # noqa
            import faiss  # noqa
            return True
        except ImportError:
            return False

    def cleanup(self) -> None:
        """Clean up resources."""
        self._save_index()
        self._save_metadata()
