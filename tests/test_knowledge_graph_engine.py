"""
Tests for the Knowledge Graph Engine — nodes, edges, traversal, social proof, niche insights.
"""

import pytest
import json

from database.schema import KnowledgeNode, KnowledgeEdge


# ─── Schema Tests ──────────────────────────────────────────────


class TestSchemaModels:
    """Verify KnowledgeNode and KnowledgeEdge models."""

    def test_node_creation(self, knowledge_graph):
        engine, db = knowledge_graph
        with db.session_scope() as s:
            node = KnowledgeNode(
                node_type="lead", node_key="lead_1",
                display_name="Joe's Plumbing",
                properties_json=json.dumps({"city": "Austin"}),
            )
            s.add(node)
            s.flush()
            assert node.id is not None

    def test_edge_creation(self, knowledge_graph):
        engine, db = knowledge_graph
        with db.session_scope() as s:
            n1 = KnowledgeNode(node_type="lead", node_key="l1")
            n2 = KnowledgeNode(node_type="agent", node_key="a1")
            s.add_all([n1, n2])
            s.flush()

            edge = KnowledgeEdge(
                from_node_id=n1.id, to_node_id=n2.id,
                edge_type="contacted_by", weight=1.0,
            )
            s.add(edge)
            s.flush()
            assert edge.id is not None


# ─── Node Operations ──────────────────────────────────────────


class TestNodeOperations:
    """Test upsert_node and get_node."""

    def test_upsert_creates_node(self, knowledge_graph):
        engine, db = knowledge_graph
        result = engine.upsert_node("niche", "plumbing", "Plumbing", {"avg_score": 7})
        assert result["success"] is True
        assert result["data"]["node_type"] == "niche"

    def test_upsert_updates_existing(self, knowledge_graph):
        engine, db = knowledge_graph
        engine.upsert_node("company", "acme", "Acme Corp", {"size": "small"})
        engine.upsert_node("company", "acme", "Acme Corporation", {"revenue": "1M"})

        result = engine.get_node("company", "acme")
        assert result["success"] is True
        assert result["data"]["display_name"] == "Acme Corporation"
        assert result["data"]["properties"]["size"] == "small"
        assert result["data"]["properties"]["revenue"] == "1M"

    def test_get_nonexistent_node(self, knowledge_graph):
        engine, db = knowledge_graph
        result = engine.get_node("company", "nonexistent_999")
        assert result["success"] is False


# ─── Edge Operations ──────────────────────────────────────────


class TestEdgeOperations:
    """Test add_edge and auto-node creation."""

    def test_add_edge(self, knowledge_graph):
        engine, db = knowledge_graph
        result = engine.add_edge(
            "lead", "edge_lead_1", "niche", "edge_plumbing",
            "belongs_to", weight=1.0,
        )
        assert result["success"] is True
        assert result["data"]["edge_type"] == "belongs_to"

    def test_add_edge_auto_creates_nodes(self, knowledge_graph):
        engine, db = knowledge_graph
        engine.add_edge("lead", "auto_lead", "agent", "auto_agent", "contacted_by")

        n1 = engine.get_node("lead", "auto_lead")
        n2 = engine.get_node("agent", "auto_agent")
        assert n1["success"] is True
        assert n2["success"] is True


# ─── Traversal ─────────────────────────────────────────────────


class TestTraversal:
    """Test get_related_entities traversal."""

    def test_get_related(self, knowledge_graph):
        engine, db = knowledge_graph
        engine.upsert_node("lead", "trav_lead", "Trav Lead")
        engine.upsert_node("niche", "trav_hvac", "HVAC")
        engine.add_edge("lead", "trav_lead", "niche", "trav_hvac", "belongs_to")
        engine.add_edge("lead", "trav_lead", "agent", "trav_closer", "contacted_by")

        result = engine.get_related_entities("lead", "trav_lead")
        assert result["success"] is True
        assert len(result["data"]) == 2

    def test_filter_by_edge_type(self, knowledge_graph):
        engine, db = knowledge_graph
        engine.add_edge("lead", "filt_lead", "niche", "filt_niche", "belongs_to")
        engine.add_edge("lead", "filt_lead", "agent", "filt_agent", "contacted_by")

        result = engine.get_related_entities("lead", "filt_lead", edge_types=["belongs_to"])
        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["edge_type"] == "belongs_to"

    def test_nonexistent_node_traversal(self, knowledge_graph):
        engine, db = knowledge_graph
        result = engine.get_related_entities("lead", "does_not_exist_999")
        assert result["success"] is False


# ─── Social Proof ──────────────────────────────────────────────


class TestSocialProof:
    """Test social proof discovery."""

    def test_find_social_proof(self, knowledge_graph):
        engine, db = knowledge_graph
        engine.upsert_node("niche", "sp_roofing", "Roofing")
        engine.upsert_node("lead", "sp_lead_1", "Roofer A", {"converted": True, "city": "Austin"})
        engine.upsert_node("lead", "sp_lead_2", "Roofer B", {"converted": False, "city": "Austin"})
        engine.add_edge("lead", "sp_lead_1", "niche", "sp_roofing", "belongs_to")
        engine.add_edge("lead", "sp_lead_2", "niche", "sp_roofing", "belongs_to")

        result = engine.find_social_proof("sp_roofing")
        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["display_name"] == "Roofer A"

    def test_social_proof_city_filter(self, knowledge_graph):
        engine, db = knowledge_graph
        engine.upsert_node("niche", "sp2_elec", "Electrical")
        engine.upsert_node("lead", "sp2_a", "Elec A", {"converted": True, "city": "Austin"})
        engine.upsert_node("lead", "sp2_b", "Elec B", {"converted": True, "city": "Dallas"})
        engine.add_edge("lead", "sp2_a", "niche", "sp2_elec", "belongs_to")
        engine.add_edge("lead", "sp2_b", "niche", "sp2_elec", "belongs_to")

        result = engine.find_social_proof("sp2_elec", city="Austin")
        assert len(result["data"]) == 1
        assert result["data"][0]["display_name"] == "Elec A"


# ─── Niche Insights ───────────────────────────────────────────


class TestNicheInsights:
    """Test niche-level analytics."""

    def test_niche_insights(self, knowledge_graph):
        engine, db = knowledge_graph
        engine.upsert_node("niche", "ni_plumb", "Plumbing")
        for i in range(5):
            converted = i < 2
            engine.upsert_node("lead", f"ni_lead_{i}", f"Lead {i}", {"converted": converted})
            engine.add_edge("lead", f"ni_lead_{i}", "niche", "ni_plumb", "belongs_to")

        result = engine.get_niche_insights("ni_plumb")
        assert result["success"] is True
        assert result["data"]["total_leads"] == 5
        assert result["data"]["converted"] == 2
        assert result["data"]["conversion_rate"] == 0.4

    def test_empty_niche(self, knowledge_graph):
        engine, db = knowledge_graph
        result = engine.get_niche_insights("nonexistent_niche_999")
        assert result["data"]["total_leads"] == 0


# ─── Interaction Recording ────────────────────────────────────


class TestInteractions:

    def test_record_interaction(self, knowledge_graph):
        engine, db = knowledge_graph
        result = engine.record_interaction(
            lead_id=1, agent_id=2,
            interaction_type="email_sent", outcome="delivered",
        )
        assert result["success"] is True


# ─── Competitors ──────────────────────────────────────────────


class TestCompetitors:

    def test_get_competitors(self, knowledge_graph):
        engine, db = knowledge_graph
        engine.add_edge("company", "comp_a", "company", "comp_b", "competitor_of")
        engine.add_edge("company", "comp_a", "company", "comp_c", "competitor_of")

        result = engine.get_competitors("comp_a")
        assert result["success"] is True
        assert len(result["data"]) == 2


# ─── Stats ────────────────────────────────────────────────────


class TestStats:

    def test_graph_stats(self, knowledge_graph):
        engine, db = knowledge_graph
        engine.upsert_node("niche", "stat_niche", "Test")
        engine.add_edge("lead", "stat_lead", "niche", "stat_niche", "belongs_to")

        result = engine.get_graph_stats()
        assert result["success"] is True
        assert result["data"]["total_nodes"] > 0
        assert result["data"]["total_edges"] > 0
