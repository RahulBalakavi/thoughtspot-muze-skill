---
name: thoughtspot-muze-dashboard
description: Create any kind of custom-designed ThoughtSpot chart on a liveboard using Muze ("muse") — ThoughtSpot's custom-chart engine (CUSTOM_CHART viz with base64 JS/CSS/HTML). Use when the user asks for a "muse chart", a "muse-based liveboard", a custom-styled/bespoke chart or leaderboard on a liveboard, or hands over a design (mockup, palette, layout) that native ThoughtSpot chart types can't match. Covers the clone-a-working-example workflow, the hand-rendered-HTML path with the render-complete sink trick, per-source column resolution, copy-first verification, and rollback.
---

# Muse (Muze) chart creation on ThoughtSpot liveboards

"Muse" = **Muze**, ThoughtSpot's custom-chart engine. A Muze chart is a liveboard viz whose
`answer.chart.type == "CUSTOM_CHART"`, carrying its **JavaScript / CSS / HTML base64-encoded
inside `chart.custom_visual_props`**. At render time the tile loads a
`muze-studio.vercel.app` iframe that executes your JS against the tile's query result — so you
get pixel-level design control (custom tables, in-cell bars, bespoke palettes, arbitrary HTML)
that native chart types can't offer.

Assumes you can call the ThoughtSpot REST API v2 (auth token, TML export/import, `metadata/search`) and know its search-query syntax. Everything below is Muze-specific.

## Typical invocation

The user hands over a **design** — a mockup, a palette, "leaderboard with in-cell score bars",
"make this tile look like X". Your job:

1. Translate the design into (a) a ThoughtSpot `search_query` that produces the needed
   rows/columns and (b) JS/CSS/HTML that paints them.
2. Decide the rendering path (below).
3. Build → import on a **copy** → verify in a real browser → apply to live.

## Two rendering paths — pick deliberately

| Path | When | How |
|---|---|---|
| **Muze API** (`muze.canvas().rows(...).columns(...).layers(...)`) | Standard shapes: bars, stacked bars, donuts | Snippets A–C in [references/muze-starter.md](references/muze-starter.md). ⚠️ `.color({field,range})` is **ignored** by the DYOC renderer — color via CSS (`.muze-layer-bar rect{fill:#2BB8C9!important}`) or numeric per-series selectors `g.muze-layer-bar-<idx> rect` |
| **Hand-rendered HTML** (bypass Muze, build DOM from `getDataFromSearchQuery().getData()`) | Table-like or bespoke designs (leaderboards, custom cards) — full control, sidesteps the `.color()` bug | The canonical template: [examples/convert_tiles_to_muze.py](examples/convert_tiles_to_muze.py). **Requires the `#sink` trick (below) or the spinner never clears** |

### The render-complete sink (mandatory on the HTML path)

ThoughtSpot decides a tile finished by watching **Muze's own render lifecycle**. Hand-painted
DOM never signals it, so the loading spinner sits forever on top of a table that already drew.
Mount a throwaway canvas offscreen purely to emit the signal:

```js
try { muze.canvas().rows([]).columns([]).data(dm).mount("#sink"); } catch (ignored) {}
```
```html
<div id="chart"></div>
<div id="sink" style="position:absolute;left:-9999px;top:0;width:8px;height:8px;overflow:hidden"></div>
```

Never add a `MutationObserver` that repaints what it observes — it can freeze the renderer.

## Workflow

### 1. Get a working example chart block to clone

The chart block carries opaque fields (`client_state`, `client_state_v2` with
`"version": "V4DOT2"`, `custom_chart_name`) you must **not** hand-author. Clone a block
ThoughtSpot itself produced:

- Vendored copy: [references/muze_example_chart.json](references/muze_example_chart.json)
  (an example viz "Completion by Course" exported from a ThoughtSpot liveboard; replace the
  worksheet fqn/name with your own and keep the `chart` block as-is).
- Or re-fetch: `metadata/search` with `{"type":"LIVEBOARD","name_pattern":"%Completion%"}`,
  export TML, scan for `chart.type == "CUSTOM_CHART"`. Don't scan all liveboards — it times
  out; use name patterns.

The custom-chart provider (a Muze Studio) is registered cluster-side; on the cluster this was
built against, the provider-management APIs (`customization/custom-actions`, `charts/search`)
404'd, so cloning was the only way to mint new Muze vizzes.

### 2. Build the chart block

```python
def muze_chart(example_chart, cols, js, css, html):
    chart = json.loads(json.dumps(example_chart))     # deep-clone the working example
    chart["type"] = "CUSTOM_CHART"
    chart["chart_columns"] = [{"column_id": c} for c in cols]
    chart["custom_chart_config"] = [{"key": "basic",
                                     "dimensions": [{"key": "fields", "columns": cols}]}]
    chart["custom_visual_props"] = json.dumps({"clientState": json.dumps({
        "version": 1,
        "playground": {"version": "v1", "code": {
            "jsCodeBase64": b64(js), "cssCodeBase64": b64(css),
            "htmlCodeBase64": b64(html)}},
    })})
    return chart
```

**Encoding**: `custom_visual_props` is a JSON *string* whose `clientState` value is itself a
JSON *string* (double-serialized). Get this wrong and the tile silently renders nothing.

Then on the target viz's `answer`:
- `search_query` — bracket-token syntax with filters, sort, and `top N`
  (e.g. `[User Email] [avg_score_latest_2] [total_sessions] [Dim Id] = 'x' sort by [avg_score_latest_2] descending top 10`)
- `display_mode = "CHART_MODE"`, `answer_columns = [{"name": ...}]` (display names!),
  `answer.pop("table")`, and `tables[0]` pointing at the source view/worksheet fqn.

For a **brand-new viz** (vs converting an existing tile): allocate `Viz_<max+1>`, append to
`liveboard["visualizations"]`, and add a layout tile or import fails — full pattern in
[examples/add_new_muze_viz.py](examples/add_new_muze_viz.py).

### 3. Column names: resolve per tile, never guess

- `answer_columns` and the JS-visible `schema[i].name` use **display names** of aggregates:
  `count` → `Number of X`, `sum` → `Total X`, `average` → `Average X`.
- Different source views name the same concept differently (`total_sessions` vs
  `session_count`) — resolve the tokens **from each tile's own source** and bake them into
  that tile's JS.
- In JS, match `schema[i].name` with a **type-based fallback** (first `dimension` / nth
  `measure`) so a rename degrades instead of breaking, and wrap everything in try/catch that
  renders `e.message` into the tile — never fail silently.

### 4. Copy-first, verify, then live

1. Make/keep a **copy liveboard** (TML import with `create_new: true`); every script targets
   the copy by default and takes a `--live` flag.
2. **Backup** the fresh export to a `backup/` dir before mutating, and **diff it against your
   last backup first** — humans hand-edit these boards concurrently; also check each touched
   tile's `answer.tables[0]` still points where you think (a repointed source with the wrong
   grain silently multiplies counts).
3. Import with `create_new: false`, then verify API-side: re-export and assert
   `chart.type == "CUSTOM_CHART"` + `custom_visual_props` non-empty (not stripped), and
   `POST /api/rest/2.0/metadata/liveboard/data {"metadata_identifier": <guid>}` returns
   `data_rows > 0` with no `error` per tile (contents are keyed by `viz_guid`, not `Viz_N`).
4. **Browser-verify before touching live — API checks can't prove pixels.** Open
   `https://<your-instance>.thoughtspot.cloud/#/insights/pinboard/<guid>[/tab/<tab_guid>]`, wait
   **30–50s** via repeated short `wait` actions (tiles are blank mid-load; each one
   cold-loads the vercel studio + Muze bundle, so slow first paint is bootstrap, not data).
   Do NOT sleep with long `setTimeout`s inside a single JS eval — it blows the CDP budget
   and masquerades as a frozen renderer. ThoughtSpot's own PNG export caches per-GUID; don't
   trust it.
5. Re-run the same script with `--live`.

Rollback: [examples/revert_muze.py](examples/revert_muze.py) — re-import the backup (guard:
assert `tml["guid"] == target`), then confirm every tile returns rows again.

## Known limitations (tell the user when relevant)

- Muze tiles **can't be exported** (CSV/PNG/PDF).
- Any template-based `provision` re-run **wipes** Muze charts — boards with them become
  hand-maintained. Do Muze last.
- Per-tile cold-load is multi-second (renderer bootstrap, ~0.6s query). If unacceptable:
  native table with conditional formatting, or self-host via `@thoughtspot/ts-chart-sdk`
  (needs admin provider registration — a separate project).
- In the ThoughtSpot console you see **all tenants' data** on multi-org setups (the app embed injects an
  org runtime filter; the console doesn't). Expected — not a leak.

## Design language (house defaults)

From the engagement-dashboard mockups — full palette and snippets in
[references/muze-starter.md](references/muze-starter.md):
DM Sans, text `#191919`, muted `#7F7E7C`, no gridlines, tabular numerals.
Score tones: ≥2.5 `#3DD9A0` · ≥2.0 `#2BB8C9` · ≥1.5 `#FFB712` · else `#E0648C`.
Status palette: Completed `#3DD9A0`, Completed Late `#FFB712`, In Progress `#2BB8C9`,
Due Soon `#6EE5F0`, Not Started `#C9C8C4`.

## Bundled files

- [examples/convert_tiles_to_muze.py](examples/convert_tiles_to_muze.py) — **canonical
  template** (browser-verified in prod): converts tiles to a hand-rendered Muze leaderboard
  table; per-source column resolution, filter preservation
  (`re.compile(r"\[[^\]]+\]\s*(?:=|!=)\s*'[^']*'")`), sink trick, copy/`--live`, backup +
  verify. Adapt this, don't start from scratch.
- [examples/add_new_muze_viz.py](examples/add_new_muze_viz.py) — add a brand-new Muze viz +
  layout tile (viz-id allocation, tab placement, re-runnable).
- [examples/revert_muze.py](examples/revert_muze.py) — restore from backup with verification.
- [references/muze_example_chart.json](references/muze_example_chart.json) — donor
  `{id, answer, viz_guid}` with a ThoughtSpot-produced CUSTOM_CHART block to clone.
- [references/muze-starter.md](references/muze-starter.md) — Muze API snippets (bar / donut /
  stacked bar), palette, how to open Muze Studio in the UI.
- [references/renderer-architecture.md](references/renderer-architecture.md) — how the
  vercel-iframe renderer works, the pale-bar CSS fix, example TMLs.

Note: the example scripts read config from env vars (`THOUGHTSPOT_HOST`, `THOUGHTSPOT_USERNAME`,
`THOUGHTSPOT_SECRET_KEY`, `MUZE_COPY_GUID`, `MUZE_LIVE_GUID`, ...); set those and adapt the
column tokens/view names to your worksheets. If your WAF blocks urllib's default UA, send
`User-Agent: Mozilla/5.0 Chrome/126`.
