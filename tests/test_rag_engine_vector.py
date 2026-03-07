"""
Tests for the Advanced RAG Engine — vector store, multi-collection, interactions, learnings.
Tests work regardless of whether ChromaDB is installed (fallback to TF-IDF).
"""

import pytest
from core.rag_engine import RAGEngine


@pytest.fixture
def rag(db_full):
    """RAG engine backed by in-memory DB."""
    return RAGEngine(db_full), db_full


# ─── Initialization & Properties ──────────────────────────────


class TestInitialization:
    """Test RAG engine initialization and backend detection."""

    def test_engine_creates(self, rag):
        engine, db = rag
        assert engine is not None

    def test_has_vector_store_attribute(self, rag):
        engine, _ = rag
        # Should be a bool — True if ChromaDB is installed, False otherwise
        assert isinstance(engine.has_vector_store, bool)

    def test_collections_initialized_or_empty(self, rag):
        engine, _ = rag
        if engine.has_vector_store:
            assert len(engine._collections) == 4
        else:
            assert len(engine._collections) == 0


# ─── Store & Query (generic) ─────────────────────────────────


class TestStoreAndQuery:
    """Test the generic store/query interface."""

    def test_store_to_emails_collection(self, rag):
        engine, _ = rag
        result = engine.store("emails", "Subject: Hello\n\nGreat email body here")
        assert result["success"] is True
        assert "doc_id" in result

    def test_store_empty_text_fails(self, rag):
        engine, _ = rag
        result = engine.store("emails", "")
        assert result["success"] is False

    def test_store_with_metadata(self, rag):
        engine, _ = rag
        result = engine.store("emails", "Test email content", {
            "reply_received": True,
            "lead_id": 42,
        })
        assert result["success"] is True

    def test_query_empty_returns_empty(self, rag):
        engine, _ = rag
        result = engine.query("emails", "")
        assert result["success"] is True
        assert result["data"] == []

    def test_store_then_query_emails(self, rag):
        engine, _ = rag
        # Store a few emails
        engine.store("emails", "Subject: Plumbing services offer for your business")
        engine.store("emails", "Subject: HVAC maintenance special pricing for you")

        # Query — result depends on backend
        result = engine.query("emails", "plumbing services")
        assert result["success"] is True
        # Might find results or not depending on similarity threshold
        assert isinstance(result["data"], list)

    def test_store_returns_doc_id(self, rag):
        engine, _ = rag
        r1 = engine.store("emails", "Unique content A")
        r2 = engine.store("emails", "Unique content B")
        assert r1["doc_id"] != r2["doc_id"]


# ─── Interactions Collection ──────────────────────────────────


class TestInteractions:
    """Test interaction storage."""

    def test_store_interaction(self, rag):
        engine, _ = rag
        result = engine.store_interaction(
            lead_id=1, interaction_type="email_sent",
            content="Sent cold email about plumbing services",
            outcome="delivered",
        )
        assert result["success"] is True

    def test_store_interaction_with_metadata(self, rag):
        engine, _ = rag
        result = engine.store_interaction(
            lead_id=2, interaction_type="reply_received",
            content="Thanks for reaching out, interested!",
            outcome="positive",
            metadata={"campaign_id": 5},
        )
        assert result["success"] is True


# ─── Agent Learnings Collection ───────────────────────────────


class TestAgentLearnings:
    """Test agent learning storage."""

    def test_store_agent_learning(self, rag):
        engine, _ = rag
        result = engine.store_agent_learning(
            agent_id=1, learning_type="timing",
            content="Emails sent between 9-10am get 2x more replies",
        )
        assert result["success"] is True

    def test_store_learning_with_metadata(self, rag):
        engine, _ = rag
        result = engine.store_agent_learning(
            agent_id=2, learning_type="content",
            content="Mentioning specific pain points increases response rate",
            metadata={"niche": "plumbing", "evidence_count": 15},
        )
        assert result["success"] is True


# ─── Success Factors ──────────────────────────────────────────


class TestSuccessFactors:
    """Test success factor extraction."""

    def test_extract_success_factors(self, rag):
        engine, _ = rag
        result = engine.extract_success_factors(
            email_text="Hi, we noticed your plumbing business lacks online presence.",
            reply_text="Thanks! Yes, we'd love to discuss.",
        )
        assert result["success"] is True


# ─── RAG Feedback ─────────────────────────────────────────────


class TestFeedback:
    """Test RAG feedback tracking."""

    def test_track_feedback(self, rag):
        engine, _ = rag
        # Store first, then track feedback
        r = engine.store("emails", "Test email for feedback tracking")
        doc_id = r.get("doc_id", "test_doc")

        result = engine.track_rag_feedback(doc_id, led_to_reply=True)
        assert result["success"] is True


# ─── Backward Compatibility ───────────────────────────────────


class TestBackwardCompat:
    """Ensure existing public methods still work."""

    def test_store_successful_email(self, rag):
        engine, _ = rag
        # Should not raise
        engine.store_successful_email(
            lead_id=1, subject="Test", body="Hello world", reply_received=True
        )

    def test_find_similar_successful_emails(self, rag):
        engine, _ = rag
        engine.store_successful_email(
            lead_id=1, subject="Plumbing offer", body="We help plumbers grow online"
        )
        result = engine.find_similar_successful_emails("plumbing services online")
        assert isinstance(result, list)

    def test_build_rag_context(self, rag):
        engine, _ = rag
        context = engine.build_rag_context({
            "business_name": "Joe's Plumbing", "category": "plumber", "city": "Austin"
        })
        assert isinstance(context, str)

    def test_get_stats(self, rag):
        engine, _ = rag
        stats = engine.get_stats()
        assert "total" in stats
        assert "replied" in stats

    def test_clear_all(self, rag):
        engine, _ = rag
        engine.store_successful_email(lead_id=1, subject="X", body="Y")
        engine.clear_all()
        stats = engine.get_stats()
        assert stats["total"] == 0

    def test_collection_stats(self, rag):
        engine, _ = rag
        stats = engine.get_collection_stats()
        assert isinstance(stats, dict)
