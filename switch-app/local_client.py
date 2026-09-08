"""
Local data layer --- same nodes/links shape and the same function names/
signatures the six-screen UX already calls, but backed by data/tree.json
on disk instead of a live Supabase project over HTTP.

This file is a drop-in replacement for supabase_client.py: every public
function below has the identical name, signature, and return shape as
its counterpart there (see that file's docstrings for the full
rationale on each shim). ui_components.py and pages/*.py import from
here unchanged in spirit --- only the `from supabase_client import ...`
lines become `from local_client import ...`; nothing about how those
files CALL these functions changes.

What's genuinely different, because there's no live database or network:
  - No RPC calls, no requests library, no SUPABASE_URL/ANON_KEY.
  - Ads, notifications, device registration: the real schema handled
    these server-side via fn_get_ads_for_device / fn_register_device.
    There is no ads table in this local file, so fetch_feed() returns
    an empty list (the Home screen already hides that section when
    empty --- same fallback behavior as the "no ad configured" case
    would have hit against live Supabase). register_device() is a
    no-op that returns None rather than silently fabricating ad data.
  - device_token still exists (kept for interface parity and because
    save_bookmark/fetch_saved key off session state, not the token)
    but no longer round-trips to a server anywhere.
  - fn_search_tree's server-side search is reimplemented in Python as
    a plain substring match over node names and link titles/urls ---
    functionally the same "search the whole tree" contract, just
    computed locally instead of via Postgres RPC.
"""
import uuid
from pathlib import Path
from typing import Optional

import streamlit as st

from tree_store import get_store

# ---------------------------------------------------------------------------
# Device identity (kept for interface parity; no server round-trip locally)
# ---------------------------------------------------------------------------

def get_or_create_device_token() -> str:
    params = st.query_params
    token = params.get("device")
    if not token:
        token = str(uuid.uuid4())
        st.query_params["device"] = token
    return token


def register_device(device_token: str, home_node_id: Optional[str] = None):
    """No-op locally --- there's no server-side device table to register
    against. Kept as a function (rather than removed) so app.py's call
    site needs no change."""
    return None


# ---------------------------------------------------------------------------
# Shims matching the ORIGINAL app's exact function names/signatures.
# ---------------------------------------------------------------------------

def fetch_active_courses(student_id: str = "demo-student"):
    """Same contract as supabase_client.fetch_active_courses: returns the
    root of the tree, or a home node's children if one is set."""
    store = get_store()
    home_node_id = st.session_state.get("home_node_id")
    nodes = store.children_of(home_node_id) if home_node_id else store.roots()
    return [store.node_to_course_shape(n) for n in nodes]


def fetch_recently_viewed(student_id: str = "demo-student"):
    """No view-history table exists locally either --- same honest empty
    list as the Supabase version, for the same reason (Home already
    hides this section when empty)."""
    return []


def fetch_feed(department: Optional[str] = None):
    """No ads table exists in the local store, so this is an empty feed.
    See module docstring."""
    return []


def fetch_saved(student_id: str = "demo-student"):
    """Session-local save, identical to the Supabase version --- this was
    already a client-side-only feature there, not a real change here."""
    return st.session_state.get("_session_bookmarks", [])


def save_bookmark(resource: dict):
    """Session-local save --- see fetch_saved()'s docstring."""
    saved = st.session_state.get("_session_bookmarks", [])
    if not any(r["id"] == resource["id"] for r in saved):
        saved.append(resource)
    st.session_state["_session_bookmarks"] = saved


def fetch_resource(resource_id: str):
    """Same fallback order as the Supabase version: check session state
    buckets first (covers the ad-feed and Saved-list paths), then the
    local node/link store directly (a case the original never needed
    because Supabase held the canonical copy; here the JSON file does)."""
    for bucket_key in ("_last_opened_resource", "_session_bookmarks"):
        bucket = st.session_state.get(bucket_key)
        if isinstance(bucket, dict) and bucket.get("id") == resource_id:
            return bucket
        if isinstance(bucket, list):
            for r in bucket:
                if r["id"] == resource_id:
                    return r

    store = get_store()
    link = store.link_by_id(resource_id)
    if link:
        node = store.node_by_id(link["node_id"])
        node_name = node["name"] if node else ""
        return store.link_to_resource_shape(link, node_name)

    return {"id": resource_id, "title": "Resource", "course_code": "---", "file_type": "link"}


def search_courses(query: str):
    """Node-type hits only, reshaped to {id, code, name} --- same filtered
    view the Supabase version exposed, computed locally instead of via
    fn_search_tree."""
    if not query:
        return []
    store = get_store()
    node_hits, _link_hits = store.search(query)
    return [
        {"id": n["id"], "code": store.node_path_label(n)[:12], "name": n.get("name", "")}
        for n in node_hits
    ]


def search_tree(query: str):
    """Full search --- both node and link hits --- for screens that want
    the complete picture, mirroring what fn_search_tree exposed."""
    if not query:
        return [], []
    return get_store().search(query)


def fetch_children_as_resources(node_id: str):
    """Same branch-on-folder-vs-leaf contract as the Supabase version."""
    store = get_store()
    children = store.children_of(node_id)
    if children:
        return "nodes", [store.node_to_course_shape(n) for n in children]

    node = store.node_by_id(node_id)
    node_name = node.get("name", "") if node else ""
    links = store.links_for_node(node_id)
    return "links", [store.link_to_resource_shape(link, node_name) for link in links]
