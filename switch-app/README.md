# Switch — local-data build

This is the six-screen "Switch" UX prototype (Home / My Courses / Course
Detail / Upload / Saved / Viewer), wired to the course-content spreadsheet
instead of a live Supabase project. No external database, no network calls
at runtime — everything reads from a JSON file bundled in the repo.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

## What changed vs. the original prototype, and why

The original code (`ui_components.py`, `app.py`, all six `pages/*.py`) called
into `supabase_client.py`, which made live HTTP requests to a Supabase
project and Postgres RPC functions (`fn_get_unit_links`, `fn_search_tree`,
etc.). That requires a real database and real credentials.

To run without either, `supabase_client.py` is replaced by two new files:

- **`tree_store.py`** — loads `data/tree.json` once and provides tree
  lookups (roots, children-of, search) plus the same `_node_to_*`/`_link_to_*`
  reshaping the original file did.
- **`local_client.py`** — same function names and return shapes as
  `supabase_client.py` (`fetch_active_courses`, `search_courses`,
  `fetch_children_as_resources`, `save_bookmark`, etc.), but computed from
  `tree_store.py` instead of an HTTP round-trip.

**Every UX file's only change is its import line** — `from supabase_client
import ...` became `from local_client import ...`. No widget, no CSS, no
session-state key, no page layout was touched. Two exceptions, both bugs
in the delivered source rather than intentional edits, called out here
instead of silently fixed:

1. **`pages/2_My_Courses.py`** — the source doc named this file
   `2_My_Course.py` (singular), but every reference to it elsewhere
   (`ui_components.py`'s bottom nav, the nav tuple itself) uses the plural
   `2_My_Courses.py`. Kept as delivered here would mean the "My Courses"
   tab 404s. Renamed to match what the rest of the app actually calls.
2. **`ui_components.py`'s docstring** — one word changed ("database" layer
   description references `local_client.save_bookmark()` instead of
   `supabase_client.save_bookmark()`) since the docstring was pointing at
   a function that no longer exists under that name.

Nothing else was rewritten, restructured, or restyled.

## The data

`data/tree.json` was generated from the uploaded `repo_5.xlsx` by
`tools/import_content.py`. Re-run it if the spreadsheet changes:

```bash
python tools/import_content.py path/to/repo_5.xlsx
```

The importer:
- builds the node tree from each row's `path` column (University → Faculty
  → Department → Year → Semester → Course Unit → leaf marker — **7 levels**
  in this file, not the 8 the original UX spec describes; see caveat below)
- normalizes `link_kind` casing/separators (`drive_Notes`, `drive-Notes` →
  `drive_notes`)
- forward-fills blank `path` and `Class Title` cells (the source file only
  states these once per group of 2–3 rows)
- silently drops rows missing a `url` or an unrecognized `link_kind` (212 of
  339 rows in the current file — mostly `youtube` rows with no URL yet, and
  fully blank spacer rows)
- generates deterministic ids (uuid5 from path/kind/url), so re-running the
  import on an unchanged file produces byte-identical output

Current import: **24 nodes, 127 links**.

### Caveat worth knowing about

In `repo_5.xlsx`, every row's `path` ends in the literal segment `"Class"` —
there's no per-topic leaf (e.g. no separate node for "Epilepsy 2" vs.
"Meningitis"). That means all of a course unit's links (14 for
Pathophysiology, for example) land on **one shared leaf node**, distinguished
only by each link's own `title` field, not by tree position. Course Detail
will show one flat list of 14 resources under "Pathophysiology," not 14
sub-folders. This is a direct reflection of the spreadsheet's own structure,
not something the importer collapsed — if per-topic nodes are wanted, the
source file needs an 8th path segment (e.g. `.../Pathophysiology/Epilepsy 2`
instead of `.../Pathophysiology/Class`).

## What's intentionally NOT here

Matching what the original `supabase_client.py` already documented as
out of scope for the Application (not things I removed):

- **Ads / "What's New on Campus" feed** — no ads table exists locally, so
  `fetch_feed()` returns empty and that section stays hidden (same fallback
  Home already had for "no ad configured").
- **View history** — same empty-list fallback as the original.
- **Student uploads / crowdsourcing** — the Upload screen is still the
  placeholder form the original shipped; content is added by re-running the
  importer, not through the app.
- **Device registration round-trip** — `register_device()` is a no-op now;
  there's no server to register against.

## Project layout

```
app.py                  entry point — device bootstrap, routes to Home
ui_components.py        shared widgets (cards, nav, wordmark, CSS)
local_client.py         drop-in for supabase_client.py — same functions,
                         backed by tree_store.py instead of HTTP
tree_store.py           loads data/tree.json, tree-walk + search primitives
pages/
  1_Home.py
  2_My_Courses.py
  3_Course_Detail.py
  4_Upload.py
  5_Saved.py
  6_Viewer.py
tools/
  import_content.py     xlsx -> data/tree.json converter
data/
  tree.json             generated — do not hand-edit; re-run the importer
assets/manifest.json
.streamlit/config.toml
```
