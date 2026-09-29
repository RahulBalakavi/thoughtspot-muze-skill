#!/usr/bin/env python3
"""Add a Muze-rendered leaderboard as Variant D on the COPY's variants tab.

Built on the same pattern as the course-engagement boards: chart.type
CUSTOM_CHART + the `<your Muze Studio provider name>` provider, with the JS/CSS/HTML carried
base64-encoded inside custom_visual_props.clientState.

Horizontal bars (rows = user, columns = measure), mockup palette, DM Sans, no
gridlines, rounded caps. Bars are coloured by proficiency against the 0-3
rubric the tab documents (>=2 is proficient), so the chart says something the
table cannot: who is over the line.

Colour is driven from CSS on the rendered rects, not Muze's .color() -- the
DYOC renderer ignores .color() and paints its own pale default.

COPY only.
"""

import base64
import json
import os
import pathlib
import urllib.request

SP = pathlib.Path(__file__).parent
TS = os.environ.get("THOUGHTSPOT_HOST", "https://YOUR-INSTANCE.thoughtspot.cloud")
COPY = os.environ.get("MUZE_COPY_GUID", "<copy-liveboard-guid>")
VIEW_FQN = os.environ.get("MUZE_VIEW_FQN", "<guid>")
VIEW_NAME = "Leaderboard By Dimension"
EVERYTHING_R2 = os.environ.get("MUZE_EVERYTHING_R2", "<guid>")
TAB_NAME = "Leaderboard Variants"
VIZ_NAME = "Variant D — Muze table"

USER_COL = "User Email"
SCORE_COL = "Average avg_score_latest_2"
SESSIONS_COL = "Total total_sessions"
MAX_SCORE = 3  # the tab's rubric is 0-3

QUERY = (
    f"[User Email] [avg_score_latest_2] [total_sessions] "
    f"[Leaderboard Dim Type] = 'collection' "
    f"[Leaderboard Dim Id] = '{EVERYTHING_R2}' "
    f"sort by [avg_score_latest_2] descending top 10"
)

JS = (
    """
const { getDataFromSearchQuery } = viz;
(function () {
  try {
    var dm = getDataFromSearchQuery();
    var d = dm.getData();
    var schema = d.schema || [];
    var rows = d.data || [];

    function idxOf(name, kind) {
      for (var i = 0; i < schema.length; i++) {
        if (schema[i] && schema[i].name === name) return i;
      }
      // fall back by type: display names shift when a column is renamed
      for (var j = 0; j < schema.length; j++) {
        var t = (schema[j] || {}).type;
        if (kind === "dim" && t === "dimension") return j;
        if (kind === "measure" && t === "measure") return j;
      }
      return -1;
    }
    var ui = idxOf(USER_COL, "dim");
    var si = idxOf(SCORE_COL, "measure");
    var ni = idxOf(SESSIONS_COL, null);

    function tone(v) {
      return v >= 2.5 ? "#3DD9A0"
           : v >= 2.0 ? "#2BB8C9"
           : v >= 1.5 ? "#FFB712"
           : "#E0648C";
    }
    function person(email) {
      if (!email) return "";
      var local = String(email).split("@")[0];
      return local.replace(/[._-]+/g, " ")
                  .replace(/\\b[a-z]/g, function (m) { return m.toUpperCase(); });
    }

    var html = '<table class="lb"><thead><tr>'
             + '<th class="rank"></th><th>User</th>'
             + '<th class="score">Score</th><th class="num">Sessions</th>'
             + '</tr></thead><tbody>';
    rows.forEach(function (r, i) {
      var v = Number(r[si]);
      var pct = Math.max(0, Math.min(100, (v / MAX_SCORE) * 100));
      var c = tone(v);
      html += '<tr>'
        + '<td class="rank">' + (i + 1) + '</td>'
        + '<td class="who" title="' + r[ui] + '">' + person(r[ui]) + '</td>'
        + '<td class="score"><div class="track">'
        + '<div class="fill" style="width:' + pct.toFixed(1)
        + '%;background:' + c + '"></div>'
        + '</div><span class="val">' + (isFinite(v) ? v.toFixed(2) : "-") + '</span></td>'
        + '<td class="num">' + (ni >= 0 && r[ni] != null ? r[ni] : "") + '</td>'
        + '</tr>';
    });
    html += "</tbody></table>";
    document.getElementById("chart").innerHTML = html;
  } catch (e) {
    document.body.innerHTML = '<pre style="font:12px monospace;color:#BE123C">'
      + (e && e.message ? e.message : e) + "</pre>";
  }
})();
""".replace("USER_COL", json.dumps(USER_COL))
    .replace("SCORE_COL", json.dumps(SCORE_COL))
    .replace("SESSIONS_COL", json.dumps(SESSIONS_COL))
    .replace("MAX_SCORE", str(MAX_SCORE))
)

CSS = """
html,body{margin:0;padding:0;font-family:'DM Sans',sans-serif;color:#191919}
#chart{width:100vw;height:100vh;overflow:auto;padding:4px 8px;box-sizing:border-box}
table.lb{width:100%;border-collapse:collapse;font-size:13px}
table.lb th{
  text-align:left;font-weight:500;font-size:11px;letter-spacing:.04em;
  text-transform:uppercase;color:#7F7E7C;padding:6px 8px;
  border-bottom:1px solid #E4E3DE;white-space:nowrap
}
table.lb td{padding:7px 8px;border-bottom:1px solid #F2F1EE;vertical-align:middle}
table.lb tr:last-child td{border-bottom:none}
td.rank,th.rank{width:26px;color:#7F7E7C;font-variant-numeric:tabular-nums;text-align:right}
td.who{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:1px;width:38%}
th.score,td.score{width:44%}
td.score{display:flex;align-items:center;gap:8px}
.track{flex:1;height:8px;border-radius:4px;background:#F0EFEC;overflow:hidden;min-width:40px}
.fill{height:100%;border-radius:4px}
.val{font-variant-numeric:tabular-nums;color:#191919;min-width:34px;text-align:right}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;color:#7F7E7C;width:64px}
"""
HTML = '<div id="chart"></div>'


def post(path, body, tok):
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 Chrome/126"}
    if tok:
        headers["Authorization"] = "Bearer " + tok
    req = urllib.request.Request(
        TS + path, data=json.dumps(body).encode(), headers=headers
    )
    return json.loads(urllib.request.urlopen(req, timeout=600).read())


def token() -> str:
    """Full-access token from env: THOUGHTSPOT_USERNAME + THOUGHTSPOT_SECRET_KEY."""
    try:
        username, secret = os.environ["THOUGHTSPOT_USERNAME"], os.environ["THOUGHTSPOT_SECRET_KEY"]
    except KeyError as e:
        raise SystemExit(f"set {e.args[0]} in the environment")
    return post(
        "/api/rest/2.0/auth/token/full",
        {
            "username": username,
            "secret_key": secret,
            "validity_time_in_sec": 86400,
            "auto_create": False,
        },
        None,
    )["token"]


def export(guid, tok):
    res = post(
        "/api/rest/2.0/metadata/tml/export",
        {
            "metadata": [{"type": "LIVEBOARD", "identifier": guid}],
            "format_type": "JSON",
            "export_fqn": True,
        },
        tok,
    )
    return json.loads(res[0]["edoc"])


def b64(s):
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def build_chart(example_chart):
    """Clone the working Muze chart block, swapping columns and code."""
    chart = json.loads(json.dumps(example_chart))
    cols = [USER_COL, SCORE_COL, SESSIONS_COL]
    chart["chart_columns"] = [{"column_id": c} for c in cols]
    chart["custom_chart_config"] = [
        {"key": "basic", "dimensions": [{"key": "fields", "columns": cols}]}
    ]
    client_state = {
        "version": 1,
        "playground": {
            "version": "v1",
            "code": {
                "jsCodeBase64": b64(JS),
                "cssCodeBase64": b64(CSS),
                "htmlCodeBase64": b64(HTML),
            },
        },
    }
    chart["custom_visual_props"] = json.dumps({"clientState": json.dumps(client_state)})
    return chart


def main() -> None:
    tok = token()
    example = json.load((SP.parent / "references" / "muze_example_chart.json").open())

    print(f"1. exporting COPY {COPY}")
    tml = export(COPY, tok)
    with open(SP / "backup" / "liveboard_copy_PRE_MUZE.json", "w") as fh:
        json.dump(tml, fh, indent=1)
    lb = tml["liveboard"]

    template = next(
        (
            v
            for v in lb["visualizations"]
            if (v.get("answer") or {})
            .get("name", "")
            .endswith("Leaderboard (Best of Latest 2)")
        ),
        None,
    )
    if template is None:
        raise SystemExit("ABORT: no leaderboard viz to clone the answer from")
    tab = next((t for t in lb["layout"]["tabs"] if t["name"] == TAB_NAME), None)
    if tab is None:
        raise SystemExit(f"ABORT: run slice4_leaderboard_variants.py first ({TAB_NAME})")

    # re-runnable
    old = {
        v["id"]
        for v in lb["visualizations"]
        if (v.get("answer") or {}).get("name") == VIZ_NAME
    }
    lb["visualizations"] = [v for v in lb["visualizations"] if v["id"] not in old]
    tab["tiles"] = [t for t in tab["tiles"] if t["visualization_id"] not in old]

    answer = json.loads(json.dumps(template["answer"]))
    answer["name"] = VIZ_NAME
    answer["dynamic_name"] = VIZ_NAME
    answer["tables"] = [{"id": VIEW_NAME, "name": VIEW_NAME, "fqn": VIEW_FQN}]
    answer["search_query"] = QUERY
    answer["display_mode"] = "CHART_MODE"
    answer["chart"] = build_chart(example["answer"]["chart"])
    answer["answer_columns"] = [
        {"name": USER_COL},
        {"name": SCORE_COL},
        {"name": SESSIONS_COL},
    ]
    answer.pop("table", None)

    next_id = (
        max(
            int(v["id"].split("_")[1])
            for v in lb["visualizations"]
            if v["id"].startswith("Viz_") and v["id"].split("_")[1].isdigit()
        )
        + 1
    )
    viz_id = f"Viz_{next_id}"
    lb["visualizations"].append({"id": viz_id, "answer": answer})
    bottom = max(t["y"] + t["height"] for t in tab["tiles"]) if tab["tiles"] else 0
    tab["tiles"].append(
        {"visualization_id": viz_id, "x": 0, "y": bottom, "height": 8, "width": 6}
    )
    print(f"2. importing {viz_id} ({VIZ_NAME}) onto `{TAB_NAME}`")

    status = post(
        "/api/rest/2.0/metadata/tml/import",
        {
            "metadata_tmls": [json.dumps(tml)],
            "import_policy": "ALL_OR_NONE",
            "create_new": False,
        },
        tok,
    )[0]["response"]["status"]
    if status.get("status_code") == "ERROR":
        raise SystemExit(f"IMPORT FAILED: {status.get('error_message')}")
    print(f"   ok ({status.get('status_code')})")

    print("3. verifying it survived and kept its Muze payload")
    fresh = export(COPY, tok)["liveboard"]
    got = next(
        (
            v
            for v in fresh["visualizations"]
            if (v.get("answer") or {}).get("name") == VIZ_NAME
        ),
        None,
    )
    if got is None:
        raise SystemExit("ABORT: viz dropped on import")
    ch = got["answer"]["chart"]
    print(f"   chart.type            = {ch.get('type')}")
    print(f"   custom_chart_name     = {ch.get('custom_chart_name')}")
    kept = bool(ch.get("custom_visual_props"))
    print(f"   custom_visual_props   = {'preserved' if kept else 'STRIPPED'}")
    if ch.get("type") != "CUSTOM_CHART" or not kept:
        raise SystemExit("ABORT: Muze payload did not persist through import")

    data = post(
        "/api/rest/2.0/metadata/liveboard/data", {"metadata_identifier": COPY}, tok
    )
    seen = {c["visualization_id"]: c for c in data.get("contents", [])}
    c = seen.get(got.get("viz_guid"))
    rows = 0 if c is None else len(c.get("data_rows", []))
    err = None if c is None else c.get("error")
    print(f"   data                  = {rows} rows, err={err}")
    if not rows or err:
        raise SystemExit("FAILED — no data; restore backup/liveboard_copy_PRE_MUZE.json")

    print(f"\nVERIFIED — Muze variant is on the `{TAB_NAME}` tab.")
    print(f"{TS}/#/pinboard/{COPY}")


if __name__ == "__main__":
    main()
