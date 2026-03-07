"""
Aura — RAG Engine
Multi-layer Retrieval-Augmented Generation:
 - Layer 1: TF-IDF sparse vectors (always available, no extra deps)
 - Layer 2: ChromaDB + sentence-transformers dense vectors (optional)

Stores successful emails, interactions, knowledge, and agent learnings.
Retrieves similar examples to inject as context into agent prompts.
"""

import json
import math
import hashlib
from typing import List, Dict, Optional
from datetime import datetime

from database.db_manager import DatabaseManager
from database.schema import RagMemory
from config import (
    RAG_MAX_EXAMPLES, RAG_SIMILARITY_THRESHOLD,
    VECTOR_RAG_MODEL, VECTOR_RAG_COLLECTIONS,
    VECTOR_RAG_MAX_RESULTS, VECTOR_RAG_SIMILARITY_THRESHOLD,
    CHROMADB_PERSIST_DIR,
)
from utils.logger import get_logger

logger = get_logger("rag_engine")


class RAGEngine:
    """
    Store and retrieve successful email examples for style mimicry.
    Uses TF-IDF sparse vectors as default embedding strategy with
    optional upgrade to ollama nomic-embed-text.
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._idf_cache = {}  # term → idf score (rebuilt periodically)
        self._vocab_dirty = True
        # Vector store (optional — needs chromadb + sentence-transformers)
        self._chroma_client = None
        self._embedding_model = None
        self._collections = {}
        self._initialize_vector_store()

    # ─── Embedding ─────────────────────────────────────────────────

    def _get_embedding(self, text: str) -> List[float]:
        """
        Generate an embedding vector for text.
        Tries ollama nomic-embed-text first, falls back to TF-IDF sparse vector.
        """
        # Try Ollama embedding
        try:
            import httpx
            resp = httpx.post(
                "http://localhost:11434/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                embedding = data.get("embedding", [])
                if embedding:
                    return embedding
        except Exception:
            pass  # Ollama not available, fall back to TF-IDF

        # Fallback: TF-IDF sparse vector
        return self._tfidf_embedding(text)

    def _tfidf_embedding(self, text: str) -> List[float]:
        """Simple TF-IDF embedding using existing corpus vocabulary."""
        tokens = self._tokenize(text)
        if not tokens:
            return []

        # Build term frequency
        tf = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        max_tf = max(tf.values()) if tf else 1

        # Rebuild IDF if vocab is dirty
        if self._vocab_dirty:
            self._rebuild_idf()

        # Build vector using fixed vocab order
        vocab = sorted(self._idf_cache.keys())
        if not vocab:
            # No existing documents — return raw TF vector hash
            vocab = sorted(tf.keys())

        vector = []
        for term in vocab:
            tf_val = 0.5 + 0.5 * (tf.get(term, 0) / max_tf) if term in tf else 0.0
            idf_val = self._idf_cache.get(term, 1.0)
            vector.append(tf_val * idf_val)

        return vector

    def _rebuild_idf(self):
        """Rebuild IDF cache from all stored RagMemory documents."""
        try:
            with self.db_manager.session_scope() as session:
                all_docs = session.query(RagMemory.content_text).all()

            doc_count = len(all_docs) + 1  # +1 smoothing
            term_doc_freq = {}

            for (text,) in all_docs:
                unique_tokens = set(self._tokenize(text or ""))
                for t in unique_tokens:
                    term_doc_freq[t] = term_doc_freq.get(t, 0) + 1

            self._idf_cache = {
                term: math.log(doc_count / (1 + freq))
                for term, freq in term_doc_freq.items()
            }
            self._vocab_dirty = False
        except Exception as e:
            logger.warning(f"Failed to rebuild IDF: {e}")

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Basic tokenization: lowercase, alphanumeric words only."""
        import re
        return re.findall(r'\b[a-z0-9]+\b', text.lower())

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b:
            return 0.0
        # Align lengths (pad shorter with zeros)
        max_len = max(len(a), len(b))
        a = a + [0.0] * (max_len - len(a))
        b = b + [0.0] * (max_len - len(b))

        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))

        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    # ─── Storage ───────────────────────────────────────────────────

    def store_successful_email(
        self,
        lead_id: Optional[int],
        subject: str,
        body: str,
        reply_received: bool = False,
    ):
        """Store an email in RAG memory with its embedding."""
        full_text = f"Subject: {subject}\n\n{body}"
        embedding = self._get_embedding(full_text)

        try:
            with self.db_manager.session_scope() as session:
                mem = RagMemory(
                    lead_id=lead_id,
                    content_type="email",
                    content_text=full_text,
                    embedding=json.dumps(embedding),
                    reply_received=reply_received,
                    created_at=datetime.utcnow(),
                )
                session.add(mem)
            self._vocab_dirty = True
            logger.info(f"Stored email in RAG memory (lead={lead_id}, reply={reply_received})")
        except Exception as e:
            logger.error(f"Failed to store RAG memory: {e}")

    # ─── Retrieval ─────────────────────────────────────────────────

    def find_similar_successful_emails(
        self, target_text: str, limit: int = RAG_MAX_EXAMPLES
    ) -> List[Dict]:
        """
        Find the most similar successful emails (replied-to preferred).
        Returns list of {content_text, similarity, reply_received}.
        """
        target_embedding = self._get_embedding(target_text)
        if not target_embedding:
            return []

        try:
            with self.db_manager.session_scope() as session:
                # Prefer replied emails, but include all
                memories = (
                    session.query(RagMemory)
                    .filter(RagMemory.content_type == "email")
                    .order_by(RagMemory.reply_received.desc())
                    .all()
                )

            scored = []
            for mem in memories:
                try:
                    mem_embedding = json.loads(mem.embedding) if mem.embedding else []
                except (json.JSONDecodeError, TypeError):
                    continue

                sim = self._cosine_similarity(target_embedding, mem_embedding)
                if sim >= RAG_SIMILARITY_THRESHOLD:
                    scored.append({
                        "content_text": mem.content_text,
                        "similarity": round(sim, 4),
                        "reply_received": mem.reply_received,
                    })

            # Sort by reply_received (True first), then by similarity
            scored.sort(key=lambda x: (-int(x["reply_received"]), -x["similarity"]))
            return scored[:limit]

        except Exception as e:
            logger.error(f"RAG similarity search failed: {e}")
            return []

    def build_rag_context(self, lead_data: dict) -> str:
        """
        Build a context block from similar successful emails.
        Intended to be prepended to the email generation prompt.
        """
        # Build a target text from lead info
        target = (
            f"{lead_data.get('business_name', '')} "
            f"{lead_data.get('category', '')} "
            f"{lead_data.get('city', '')} "
            f"{lead_data.get('snippet', '')}"
        )

        similar = self.find_similar_successful_emails(target)
        if not similar:
            return ""

        lines = ["Here are examples of successful emails that got replies:"]
        for i, item in enumerate(similar, 1):
            replied_tag = " [GOT REPLY]" if item["reply_received"] else ""
            lines.append(f"\n--- Example {i}{replied_tag} ---")
            lines.append(item["content_text"])

        lines.append("\nMatch the style, tone, and structure of these examples.")
        return "\n".join(lines)

    # ─── Management ────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return RAG memory statistics."""
        try:
            with self.db_manager.session_scope() as session:
                from sqlalchemy import func
                total = session.query(func.count(RagMemory.id)).scalar() or 0
                replied = (
                    session.query(func.count(RagMemory.id))
                    .filter(RagMemory.reply_received == True)
                    .scalar() or 0
                )
            return {"total": total, "replied": replied}
        except Exception as e:
            logger.error(f"RAG stats error: {e}")
            return {"total": 0, "replied": 0}

    def clear_all(self):
        """Delete all RAG memory entries."""
        try:
            with self.db_manager.session_scope() as session:
                session.query(RagMemory).delete()
            self._idf_cache.clear()
            self._vocab_dirty = True
            logger.info("RAG memory cleared")
        except Exception as e:
            logger.error(f"Failed to clear RAG memory: {e}")

    def import_from_csv(self, file_path: str) -> dict:
        """Import emails from a CSV file into RAG memory."""
        import csv
        count = 0
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    subject = row.get("subject", "")
                    body = row.get("body", "")
                    replied = row.get("replied", "false").lower() in ("true", "1", "yes")
                    if body:
                        self.store_successful_email(
                            lead_id=None,
                            subject=subject,
                            body=body,
                            reply_received=replied,
                        )
                        count += 1
            return {"success": True, "imported": count}
        except Exception as e:
            logger.error(f"RAG CSV import failed: {e}")
            return {"success": False, "error": str(e), "imported": count}

    # ─── Vector Store (ChromaDB) ──────────────────────────────────

    @property
    def has_vector_store(self) -> bool:
        """True if ChromaDB + sentence-transformers are available."""
        return self._chroma_client is not None and self._embedding_model is not None

    def _initialize_vector_store(self):
        """Try to initialize ChromaDB + sentence-transformers. Silent fallback to TF-IDF."""
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            persist_dir = str(CHROMADB_PERSIST_DIR)
            self._chroma_client = chromadb.Client(chromadb.Settings(
                anonymized_telemetry=False,
                is_persistent=True,
                persist_directory=persist_dir,
            ))
            self._embedding_model = SentenceTransformer(VECTOR_RAG_MODEL)

            for coll_name in VECTOR_RAG_COLLECTIONS:
                self._collections[coll_name] = (
                    self._chroma_client.get_or_create_collection(name=coll_name)
                )

            logger.info(f"Vector store initialized: ChromaDB + {VECTOR_RAG_MODEL}")

        except ImportError:
            logger.info("ChromaDB/sentence-transformers not installed — using TF-IDF fallback")
        except Exception as e:
            logger.warning(f"Vector store init failed: {e} — using TF-IDF fallback")

    def _dense_embed(self, text: str) -> List[float]:
        """Generate dense embedding using sentence-transformers model."""
        if self._embedding_model is None:
            return []
        return self._embedding_model.encode(text).tolist()

    def _doc_id(self, text: str, prefix: str = "") -> str:
        """Generate a deterministic document ID."""
        h = hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
        return f"{prefix}_{h}" if prefix else h

    def store(self, collection: str, text: str, metadata: dict = None,
              doc_id: str = None) -> dict:
        """
        Store a document in a vector collection.
        Falls back to TF-IDF (no-op for non-email collections without ChromaDB).
        """
        if not text:
            return {"success": False, "error": "Empty text"}

        metadata = metadata or {}
        doc_id = doc_id or self._doc_id(text, collection)

        if self.has_vector_store and collection in self._collections:
            try:
                embedding = self._dense_embed(text)
                self._collections[collection].upsert(
                    ids=[doc_id],
                    documents=[text[:5000]],
                    embeddings=[embedding],
                    metadatas=[metadata],
                )
                return {"success": True, "doc_id": doc_id, "backend": "chromadb"}
            except Exception as e:
                logger.warning(f"ChromaDB store failed: {e}")

        # Fallback: store in SQLite via RagMemory (only for emails collection)
        if collection == "emails":
            embedding = self._tfidf_embedding(text)
            try:
                with self.db_manager.session_scope() as session:
                    mem = RagMemory(
                        content_type="email",
                        content_text=text[:5000],
                        embedding=json.dumps(embedding),
                        reply_received=metadata.get("reply_received", False),
                    )
                    session.add(mem)
                self._vocab_dirty = True
                return {"success": True, "doc_id": doc_id, "backend": "tfidf"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": True, "doc_id": doc_id, "backend": "memory_only"}

    def query(self, collection: str, query_text: str,
              n_results: int = VECTOR_RAG_MAX_RESULTS,
              where: dict = None) -> dict:
        """
        Query a vector collection for similar documents.
        Falls back to TF-IDF cosine search for email collection.
        """
        if not query_text:
            return {"success": True, "data": []}

        if self.has_vector_store and collection in self._collections:
            try:
                embedding = self._dense_embed(query_text)
                kwargs = {
                    "query_embeddings": [embedding],
                    "n_results": n_results,
                }
                if where:
                    kwargs["where"] = where

                results = self._collections[collection].query(**kwargs)

                items = []
                if results and results.get("documents"):
                    docs = results["documents"][0]
                    distances = results.get("distances", [[]])[0]
                    metadatas = results.get("metadatas", [[]])[0]
                    ids = results.get("ids", [[]])[0]

                    for i, doc in enumerate(docs):
                        distance = distances[i] if i < len(distances) else 1.0
                        similarity = max(0.0, 1.0 - distance)
                        if similarity >= VECTOR_RAG_SIMILARITY_THRESHOLD:
                            items.append({
                                "id": ids[i] if i < len(ids) else None,
                                "text": doc,
                                "similarity": round(similarity, 4),
                                "metadata": metadatas[i] if i < len(metadatas) else {},
                            })

                return {"success": True, "data": items, "backend": "chromadb"}
            except Exception as e:
                logger.warning(f"ChromaDB query failed: {e}")

        # Fallback: TF-IDF search (email collection only)
        if collection == "emails":
            similar = self.find_similar_successful_emails(query_text, limit=n_results)
            items = [
                {
                    "id": None,
                    "text": s["content_text"],
                    "similarity": s["similarity"],
                    "metadata": {"reply_received": s["reply_received"]},
                }
                for s in similar
            ]
            return {"success": True, "data": items, "backend": "tfidf"}

        return {"success": True, "data": [], "backend": "none"}

    def store_interaction(self, lead_id: int, interaction_type: str,
                          content: str, outcome: str = "",
                          metadata: dict = None) -> dict:
        """Store a lead interaction (email sent, reply received, call, etc.)."""
        meta = metadata or {}
        meta.update({
            "lead_id": lead_id,
            "interaction_type": interaction_type,
            "outcome": outcome,
        })
        full_text = f"[{interaction_type}] {content}"
        if outcome:
            full_text += f"\n[Outcome: {outcome}]"
        return self.store("interactions", full_text, meta)

    def store_agent_learning(self, agent_id: int, learning_type: str,
                             content: str, metadata: dict = None) -> dict:
        """Store an agent learning/insight for retrieval."""
        meta = metadata or {}
        meta.update({
            "agent_id": agent_id,
            "learning_type": learning_type,
        })
        return self.store("agent_learnings", content, meta)

    def extract_success_factors(self, email_text: str, reply_text: str) -> dict:
        """Extract what made an email get a reply by storing both for pattern matching."""
        combined = f"EMAIL:\n{email_text}\n\nREPLY:\n{reply_text}"
        result = self.store("knowledge", combined, {
            "type": "success_factor",
            "has_reply": True,
        })
        return result

    def track_rag_feedback(self, doc_id: str, led_to_reply: bool) -> dict:
        """Record feedback on whether a RAG-retrieved example led to a reply."""
        if self.has_vector_store and "emails" in self._collections:
            try:
                existing = self._collections["emails"].get(ids=[doc_id])
                if existing and existing["metadatas"]:
                    meta = existing["metadatas"][0]
                    reply_count = meta.get("reply_count", 0)
                    use_count = meta.get("use_count", 0)
                    meta["use_count"] = use_count + 1
                    if led_to_reply:
                        meta["reply_count"] = reply_count + 1
                    self._collections["emails"].update(
                        ids=[doc_id], metadatas=[meta]
                    )
                    return {"success": True, "doc_id": doc_id}
            except Exception as e:
                logger.warning(f"RAG feedback tracking failed: {e}")

        return {"success": True, "doc_id": doc_id, "note": "feedback recorded (no-op without vector store)"}

    def get_collection_stats(self) -> dict:
        """Return document counts per vector collection."""
        stats = {}
        if self.has_vector_store:
            for name, coll in self._collections.items():
                try:
                    stats[name] = coll.count()
                except Exception:
                    stats[name] = 0
        else:
            stats["backend"] = "tfidf"
            stats["emails"] = self.get_stats().get("total", 0)
        return stats
