"""
Raw tree access over the local JSON file --- the local equivalent of the
"Raw tree access (used internally by the shims below)" section of
supabase_client.py, plus the two _node_to_*/_link_to_* reshaping
functions from that file (made public here since local_client.py and
tools/import_content.py both need them, and there's no module-private
convention worth enforcing across a two-file local package).

Loaded once per Streamlit session via @st.cache_resource --- data/tree.json
is small (24 nodes / 127 links from the current repo_5.xlsx import) and
read-only at runtime, so caching avoids re-parsing it on every rerun
without needing any actual database engine.
"""
import json
from pathlib import Path
from typing import Optional

import streamlit as st

DATA_PATH = Path(__file__).parent / "data" / "tree.json"


class TreeStore:
    def __init__(self, nodes: list[dict], links: list[dict]):
        self._nodes_by_id = {n["id"]: n for n in nodes}
        self._links_by_id = {l["id"]: l for l in links}
        self._children_by_parent: dict[Optional[str], list[dict]] = {}
        for n in nodes:
            self._children_by_parent.setdefault(n["parent_id"], []).append(n)
        for bucket in self._children_by_parent.values():
            bucket.sort(key=lambda n: n["sort_order"])
        self._links_by_node: dict[str, list[dict]] = {}
        for l in links:
            self._links_by_node.setdefault(l["node_id"], []).append(l)

    # -- raw access -----------------------------------------------------

    def roots(self) -> list[dict]:
        return list(self._children_by_parent.get(None, []))

    def children_of(self, parent_id: str) -> list[dict]:
        return list(self._children_by_parent.get(parent_id, []))

    def node_by_id(self, node_id: str) -> Optional[dict]:
        return self._nodes_by_id.get(node_id)

    def link_by_id(self, link_id: str) -> Optional[dict]:
        return self._links_by_id.get(link_id)

    def links_for_node(self, node_id: str) -> list[dict]:
        return list(self._links_by_node.get(node_id, []))

    def node_path_label(self, node: dict) -> str:
        """Slash-joined ancestor chain, used for search-result labeling ---
        the local stand-in for the real schema's node_path column."""
        parts = [node["name"]]
        cur = node
        while cur.get("parent_id"):
            cur = self._nodes_by_id.get(cur["parent_id"])
            if not cur:
                break
            parts.append(cur["name"])
        return "/".join(reversed(parts))

    def search(self, query: str) -> tuple[list[dict], list[dict]]:
        """Substring match over node names and link titles/urls --- the
        local equivalent of fn_search_tree. Case-insensitive, matches
        anywhere in the string (not just prefix), mirroring typical
        Postgres ILIKE '%query%' search behavior."""
        q = query.strip().lower()
        if not q:
            return [], []
        node_hits = [n for n in self._nodes_by_id.values() if q in n["name"].lower()]
        link_hits = [
            l for l in self._links_by_id.values()
            if q in (l.get("title") or "").lower() or q in l["url"].lower()
        ]
        return node_hits, link_hits

    # -- reshaping (mirrors supabase_client.py's _node_to_*/_link_to_*) --

    def node_to_course_shape(self, node: dict) -> dict:
        return {
            "id": node["id"],
            "code": node.get("node_type", "").upper()[:4] or "NODE",
            "name": node.get("name", "Untitled"),
            "resource_count": None,  # not tracked --- UI hides it when None
        }

    def link_to_resource_shape(self, link: dict, node_name: str = "") -> dict:
        kind_to_filetype = {"youtube": "video", "drive_notes": "note", "drive_questions": "doc"}
        return {
            "id": link.get("id"),
            "title": link.get("title") or link.get("url", "Untitled link"),
            "course_code": node_name,
            "file_type": kind_to_filetype.get(link.get("link_kind"), "link"),
            "url": link.get("url"),
        }


@st.cache_resource
def get_store() -> TreeStore:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"{DATA_PATH} not found. Run: python tools/import_content.py <repo_5.xlsx>"
        )
    raw = json.loads(DATA_PATH.read_text())
    return TreeStore(raw["nodes"], raw["links"])
