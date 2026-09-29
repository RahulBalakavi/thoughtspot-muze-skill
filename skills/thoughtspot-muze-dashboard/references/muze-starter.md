# Muze Studio — starter pack (matched to the `enablement mgr metrics.html` mockup)

Goal: make the liveboard's charts look like the **mockup you shared**. Decoded the mockup's
React source — its charts are **flat solid colors with rounded *top* corners** (`borderRadius:
"5px 5px 0 0"`), a **meaningful status palette**, no gridlines, DM Sans. **Not** gradients.

## How to open Muze Studio
1. Liveboard chart tile → **Edit** (opens as an Answer) → **Change visualization** → **Muze** (code editor).
2. Three editors: **JavaScript / CSS / HTML**, live preview. → **Save** → **Pin** to the Liveboard.

Docs: [Muze Studio](https://docs.thoughtspot.com/cloud/10.14.0.cl/chart-create) · [Use Muze](https://developers.thoughtspot.com/charts/muze/use-muze) · [Gallery](https://developers.thoughtspot.com/charts/muze/Gallery/Ranking/Cross-Tab-Bar-Chart)

## ⚠️ Caveats
- **Not in TML.** A future `provision` rebuilds the liveboard from templates and **wipes** Muze charts. Do them last; don't re-provision (or accept the dashboard is now hand-maintained).
- Muze charts can't be downloaded (CSV/PNG/PDF).
- Field names below are placeholders — use the **exact column display names** in your Answer's data panel.

## Exact palette from the mockup (hex)
```
Status colours (Status Mix / stacked-by-status):
  Completed       #3DD9A0  (mint-base)
  Completed Late  #FFB712  (gold / g-500)
  In Progress     #2BB8C9  (teal-base)
  Due Soon        #6EE5F0  (teal-bright)
  Not Started     #C9C8C4  (n-150 grey)

Generic bars (ColumnChart):  solid #2BB8C9 teal, rounded top
Quiz-score buckets:  <70 #E0648C · 70–79 #FFB712 · 80–89 #2BB8C9 · 90–100 #3DD9A0
Days-late buckets:   all #FFB712 gold
Completion mini-bar: ≥80 #3DD9A0 · ≥50 #FFB712 · else #E0648C
Risk tone:           ≥8 #BE123C · ≥4 #CC8A00 · else #1A7A58
Text #191919 · muted #7F7E7C · font 'DM Sans' · NO gridlines
```

---

## Snippet A — Solid bar, rounded top (distributions, "by region/course" counts)
Mockup `ColumnChart`: solid teal, `borderRadius:"5px 5px 0 0"`, ~54px max width, gridless.

**JavaScript**
```js
const { muze, getDataFromSearchQuery } = viz;
const data = getDataFromSearchQuery();
muze.canvas()
  .columns(["Course Title"])            // X dimension (or "Region", "Quiz Score Bucket", …)
  .rows(["Total Count User Email"])     // Y measure (use the real column name)
  .layers([{ mark: "bar" }])
  .data(data)
  .config({
    gridLines: { y: { show: false }, x: { show: false } },
    axisLine:  { y: { show: false } },
  })
  .mount("#chart");
```
**CSS** — solid teal, rounded *top* corners, brand type:
```css
.muze-layer-bar path, .muze-layer-bar rect {
  fill: #2BB8C9 !important; stroke: none !important;
}
/* rounded top only — Muze renders bars as <path>; if your build supports
   bar cornerRadius use the JS config, else this rx is a fallback for <rect> */
.muze-layer-bar rect { rx: 5px; ry: 5px; }
.muze-grid text { font-family: 'DM Sans', sans-serif; fill: #7F7E7C; font-size: 11px; }
```
> For **per-bucket colours** (quiz distribution), drive colour from the bucket field:
> `.color({ field: "Quiz Score Bucket", domain: ["<70","70–79","80–89","90–100"], range: ["#E0648C","#FFB712","#2BB8C9","#3DD9A0"] })`
> and drop the CSS `fill`.

---

## Snippet B — Donut / Status Mix (exact status palette)
**JavaScript**
```js
const { muze, getDataFromSearchQuery } = viz;
const data = getDataFromSearchQuery();
muze.canvas()
  .rows([]).columns([])
  .color({
    field: "Status",
    domain: ["Completed","Completed Late","In Progress","Due Soon","Not Started"],
    range:  ["#3DD9A0","#FFB712","#2BB8C9","#6EE5F0","#C9C8C4"],
  })
  .layers([{ mark: "arc", encoding: { angle: "Total Count User Email", radius: { range: [58, 96] } } }])
  .data(data)
  .config({ legend: { position: "right" } })
  .mount("#chart");
```
**CSS**
```css
.muze-legend text, .muze-arc text { font-family: 'DM Sans', sans-serif; fill: #191919; }
```

---

## Snippet C — Stacked bar by status ("Completion by course/region")
The mockup's headline chart is a **horizontal stacked bar** per row, segments = status,
coloured by the status palette, `borderRadius: 5`.

**JavaScript**
```js
const { muze, getDataFromSearchQuery } = viz;
const data = getDataFromSearchQuery();
muze.canvas()
  .rows(["Course Title"])               // one bar per course
  .columns(["Total Count User Email"])  // length
  .color({
    field: "Status",
    domain: ["Completed","Completed Late","In Progress","Due Soon","Not Started"],
    range:  ["#3DD9A0","#FFB712","#2BB8C9","#6EE5F0","#C9C8C4"],
  })
  .layers([{ mark: "bar", transform: { type: "stack" } }])
  .data(data)
  .config({ gridLines: { x: { show: false } }, axisLine: { y: { show: false } } })
  .mount("#chart");
```
**CSS**
```css
.muze-layer-bar rect { rx: 4px; }   /* rounded segment ends */
.muze-grid text { font-family: 'DM Sans', sans-serif; fill: #7F7E7C; }
```

---

## Order of attack
Start with **one** distribution tile (Snippet A) — paste, fix the field name, confirm solid-teal
rounded-top bars on the live preview, Save + Pin. Then the donut (B) and the stacked "Completion
by course" (C). The palette/CSS carry over verbatim; only the field names change. Muze's exact
`cornerRadius`/`color` keys vary by build — the live editor autocompletes them, so tune there if a
config name differs.
