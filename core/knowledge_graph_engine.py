"""
Aura — Knowledge Graph Engine
Entity-relationship tracking for leads, companies, niches, campaigns, and agents.
Enables social proof discovery, competitor analysis, and niche insights.
"""

import json
from collections import defaultdict

from database.db_manager import DatabaseManager
from database.schema import KnowledgeNode, KnowledgeEdge
from utils.logger import get_logger

logger = get_logger("knowledge_graph_engine")


class KnowledgeGraphEngine:
    """Manages an entity-relationship knowledge graph in SQLite."""

    def __init__(self, db_manager: DatabaseManager, rag_engine=None):
        self.db_manager = db_manager
        self.rag_engine = rag_engine

    # ─── Node Operations ───────────────────────────────────────

    def upsert_node(self, node_type: str, node_key: str,
                    display_name: str = "", properties: dict = None) -> dict:
        """Create or update a knowledge node."""
        try:
            with self.db_manager.session_scope() as session:
                existing = session.query(KnowledgeNode).filter_by(
                    node_type=node_type, node_key=node_key
                ).first()

                if existing:
                    existing.display_name = display_name or existing.display_name
                    if properties:
                        old_props = json.loads(existing.properties_json or "{}")
                        old_props.update(properties)
                        existing.properties_json = json.dumps(old_props)
                    node_id = existing.id
                else:
                    node = KnowledgeNode(
                        node_type=node_type,
                        node_key=node_key,
                        display_name=display_name,
                        properties_json=json.dumps(properties or {}),
                    )
                    session.add(node)
                    session.flush()
                    node_id = node.id

            return {"success": True, "data": {"node_id": node_id, "node_type": node_type, "node_key": node_key}}

        except Exception as e:
            logger.error(f"upsert_node failed: {e}")
            return {"success": False, "error": str(e)}

    def get_node(self, node_type: str, node_key: str) -> dict:
        """Get a single node by type and key."""
        try:
            with self.db_manager.session_scope() as session:
                node = session.query(KnowledgeNode).filter_by(
                    node_type=node_type, node_key=node_key
                ).first()
                if not node:
                    return {"success": False, "error": "Node not found"}

                return {
                    "success": True,
                    "data": {
                        "id": node.id,
                        "node_type": node.node_type,
                        "node_key": node.node_key,
                        "display_name": node.display_name,
                        "properties": json.loads(node.properties_json or "{}"),
                    },
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Edge Operations ───────────────────────────────────────

    def add_edge(self, from_type: str, from_key: str,
                 to_type: str, to_key: str,
                 edge_type: str, weight: float = 1.0,
                 properties: dict = None) -> dict:
        """Add an edge between two nodes (auto-creates nodes if needed)."""
        try:
            # Ensure both nodes exist
            from_result = self.upsert_node(from_type, from_key)
            to_result = self.upsert_node(to_type, to_key)

            if not from_result["success"] or not to_result["success"]:
                return {"success": False, "error": "Failed to create/find nodes"}

            from_id = from_result["data"]["node_id"]
            to_id = to_result["data"]["node_id"]

            with self.db_manager.session_scope() as session:
                edge = KnowledgeEdge(
                    from_node_id=from_id,
                    to_node_id=to_id,
                    edge_type=edge_type,
                    weight=weight,
                    properties_json=json.dumps(properties or {}),
                )
                session.add(edge)
                session.flush()
                edge_id = edge.id

            return {"success": True, "data": {"edge_id": edge_id, "edge_type": edge_type}}

        except Exception as e:
            logger.error(f"add_edge failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── Traversal ─────────────────────────────────────────────

    def get_related_entities(self, node_type: str, node_key: str,
                             edge_types: list = None, depth: int = 1) -> dict:
        """Get entities related to a given node, optionally filtered by edge type."""
        try:
            with self.db_manager.session_scope() as session:
                source = session.query(KnowledgeNode).filter_by(
                    node_type=node_type, node_key=node_key
                ).first()
                if not source:
                    return {"success": False, "error": "Source node not found"}

                visited = set()
                results = []
                self._traverse(session, source.id, edge_types, depth, visited, results)

            return {"success": True, "data": results}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _traverse(self, session, node_id, edge_types, depth, visited, results):
        """BFS traversal of the knowledge graph."""
        if depth <= 0 or node_id in visited:
            return
        visited.add(node_id)

        query = session.query(KnowledgeEdge).filter(
            KnowledgeEdge.from_node_id == node_id
        )
        if edge_types:
            query = query.filter(KnowledgeEdge.edge_type.in_(edge_types))

        edges = query.all()
        for edge in edges:
            target = session.query(KnowledgeNode).get(edge.to_node_id)
            if target and target.id not in visited:
                results.append({
                    "node_id": target.id,
                    "node_type": target.node_type,
                    "node_key": target.node_key,
                    "display_name": target.display_name,
                    "edge_type": edge.edge_type,
                    "weight": edge.weight,
                    "properties": json.loads(target.properties_json or "{}"),
                })
                if depth > 1:
                    self._traverse(session, target.id, edge_types, depth - 1, visited, results)

    # ─── Domain Queries ────────────────────────────────────────

    def find_social_proof(self, niche: str, city: str = None) -> dict:
        """Find converted leads in a niche for social proof in outreach."""
        try:
            with self.db_manager.session_scope() as session:
                # Find niche node
                niche_node = session.query(KnowledgeNode).filter_by(
                    node_type="niche", node_key=niche
                ).first()
                if not niche_node:
                    return {"success": True, "data": []}

                # Find leads connected to this niche via "belongs_to" edges
                edges = session.query(KnowledgeEdge).filter_by(
                    to_node_id=niche_node.id, edge_type="belongs_to"
                ).all()

                proofs = []
                for edge in edges:
                    lead_node = session.query(KnowledgeNode).get(edge.from_node_id)
                    if lead_node:
                        props = json.loads(lead_node.properties_json or "{}")
                        if props.get("converted") or props.get("replied"):
                            if city and props.get("city", "").lower() != city.lower():
                                continue
                            proofs.append({
                                "node_key": lead_node.node_key,
                                "display_name": lead_node.display_name,
                                "properties": props,
                            })

            return {"success": True, "data": proofs}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_niche_insights(self, niche: str) -> dict:
        """Get aggregated insights for a niche (total leads, converted, avg score, etc.)."""
        try:
            with self.db_manager.session_scope() as session:
                niche_node = session.query(KnowledgeNode).filter_by(
                    node_type="niche", node_key=niche
                ).first()
                if not niche_node:
                    return {"success": True, "data": {"niche": niche, "total_leads": 0}}

                # Count edges to this niche
                edges = session.query(KnowledgeEdge).filter_by(
                    to_node_id=niche_node.id, edge_type="belongs_to"
                ).all()

                total = len(edges)
                converted = 0
                for edge in edges:
                    node = session.query(KnowledgeNode).get(edge.from_node_id)
                    if node:
                        props = json.loads(node.properties_json or "{}")
                        if props.get("converted"):
                            converted += 1

            return {
                "success": True,
                "data": {
                    "niche": niche,
                    "total_leads": total,
                    "converted": converted,
                    "conversion_rate": round(converted / total, 4) if total > 0 else 0.0,
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def record_interaction(self, lead_id: int, agent_id: int,
                           interaction_type: str, outcome: str = "") -> dict:
        """Record an interaction between an agent and a lead as graph edges."""
        return self.add_edge(
            "lead", str(lead_id),
            "agent", str(agent_id),
            edge_type=interaction_type,
            properties={"outcome": outcome},
        )

    def get_competitors(self, company_key: str) -> dict:
        """Find companies connected as competitors."""
        return self.get_related_entities("company", company_key, edge_types=["competitor_of"])

    def find_similar_leads(self, lead_id: int, limit: int = 10) -> dict:
        """Find leads similar to a given lead via 'similar_to' edges."""
        result = self.get_related_entities("lead", str(lead_id), edge_types=["similar_to"])
        if result["success"]:
            result["data"] = result["data"][:limit]
        return result

    # ─── Stats ─────────────────────────────────────────────────

    def get_graph_stats(self) -> dict:
        """Return counts of nodes and edges by type."""
        try:
            from sqlalchemy import func

            with self.db_manager.session_scope() as session:
                node_counts = dict(
                    session.query(KnowledgeNode.node_type, func.count(KnowledgeNode.id))
                    .group_by(KnowledgeNode.node_type).all()
                )
                edge_counts = dict(
                    session.query(KnowledgeEdge.edge_type, func.count(KnowledgeEdge.id))
                    .group_by(KnowledgeEdge.edge_type).all()
                )
                total_nodes = session.query(func.count(KnowledgeNode.id)).scalar() or 0
                total_edges = session.query(func.count(KnowledgeEdge.id)).scalar() or 0

            return {
                "success": True,
                "data": {
                    "total_nodes": total_nodes,
                    "total_edges": total_edges,
                    "nodes_by_type": node_counts,
                    "edges_by_type": edge_counts,
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
