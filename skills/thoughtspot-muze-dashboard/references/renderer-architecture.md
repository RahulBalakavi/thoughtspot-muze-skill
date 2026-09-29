# Muze renderer notes (what the DYOC tile renderer actually does)

## Architecture of the renderer
- Each chart tile = a `muze-studio.vercel.app/?debug=false` iframe (a Monaco-based
  DYOC studio). The studio editor is hidden; the chart renders in a **nested
  about:blank iframe** inside `div.preview-only-view.livaboard-view` — reach it via
  `document.querySelector('iframe').contentDocument` from the muze frame (same-process,
  NOT a separate CDP target).
- Bars are **SVG `<rect>`**, NOT canvas (`chartCanvas:[]`). So CSS `fill` applies.

## The pale-bar root cause (precise)
- The renderer IGNORES the Muze JS `.color({field,range})` for multi-series and paints
  its own PALE blue/lavender default palette (rgb(171,199,249) / (188,210,250) / ...).
- Single-series tiles looked teal because our CSS `.muze-layer-bar rect{fill:#2BB8C9}`
  (uniform) DID apply — confirmed: their fill is exactly rgb(43,184,201)=#2BB8C9.

## The fix lever (PROVEN)
Renderer emits **numeric** per-series groups: `g.muze-layer-bar-<seriesIdx>` with inner
per-datum `g.muze-layer-bar-<seriesIdx>-<datumIdx>`. NOTE: this is NUMERIC — the local
muze@1.3.2 sandbox used status-NAME classes (`muze-layer-bar-completed`); the renderer's
bundled build does NOT. Trust the renderer, not the sandbox.

Injecting `g.muze-layer-bar-1 rect{fill:#FF00FF!important}` + `g.muze-layer-bar-0 rect{fill:#0F0!important}`
into the nested doc → bars went magenta/green on Completion-by-Course AND by-Region.

## Implementation approach for Path B
- Color via **CSS fill on `g.muze-layer-bar-<N>`** (per status series) and
  `g.muze-layer-bar-<N>-<i>` (per bucket datum). DO NOT rely on JS `.color({range})`.
- ONE open risk: series-index → status mapping order. Must verify which index = which
  status once (read rendered order), then map palette to indices. Consider forcing a
  stable status order via the search query / domain so index N is deterministic.
- Donut/arc still pale — needs its own arc selector (not muze-layer-bar); TODO.

## How to inspect (recipe)
Chrome --remote-debugging-port=9222 --remote-allow-origins=* (or websocket-client
suppress_origin=True). Per muze-studio iframe target: Runtime.evaluate
`document.querySelector('iframe').contentDocument` then query `g.muze-layer-bar-*`.

