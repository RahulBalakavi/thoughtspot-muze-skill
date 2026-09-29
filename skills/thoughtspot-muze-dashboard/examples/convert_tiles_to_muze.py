#!/usr/bin/env python3
"""Convert every leaderboard tile on the board to the Muze table renderer.

Three tiles today: Overall (`Best of Latest 2 Sessions: Leaderboard`, on the
OLD undimensioned view) and the R2 Agent / Autonomy tiles (on the dimensioned
view). Each keeps its OWN source and filters -- Overall genuinely means "latest
2 sessions overall", which only the old view computes, so it is not repointed.

The two views name their session-count column differently
(`total_sessions` vs `session_count`), so column names are resolved per tile
and baked into that tile's JS rather than guessed at runtime.

COPY by default; `--live` targets the real liveboard.
"""

import base64
import json
import os
import pathlib
import re
import sys
import urllib.request

SP = pathlib.Path(__file__).parent
TS = os.environ.get("THOUGHTSPOT_HOST", "https://YOUR-INSTANCE.thoughtspot.cloud")
COPY = os.environ.get("MUZE_COPY_GUID", "<copy-liveboard-guid>")
LIVE = os.environ.get("MUZE_LIVE_GUID", "<live-liveboard-guid>")
NEW_VIEW_FQN = os.environ.get("MUZE_NEW_VIEW_FQN", "<guid>")
MAX_SCORE = 3

# per-source column tokens: (measure token, sessions token)
SOURCE_COLUMNS = {
    "Leaderboard By Dimension": ("avg_score_latest_2", "total_sessions"),
    "Leaderboard Overall": ("avg_score_latest_2", "session_count"),
}
USER_COL = "User Email"
FILTER_RE = re.compile(r"\[[^\]]+\]\s*(?:=|!=)\s*'[^']*'")

JS_TEMPLATE = """
const { muze, getDataFromSearchQuery } = viz;
(function () {
  try {
    var dm = getDataFromSearchQuery();

    // The harness watches Muze's own render lifecycle to decide the tile has
    // finished. Painting our own DOM never signals that, so its spinner stays
    // up forever on top of a table that already drew. Mount a real canvas
    // offscreen purely to emit that signal.
    try {
      muze.canvas().rows([]).columns([]).data(dm).mount("#sink");
    } catch (ignored) {
      // signal is best-effort: a spinner is better than no table
    }

    var d = dm.getData();
    var schema = d.schema || [];
    var rows = d.data || [];
    var NAMES = __NAMES__;
    var MAX = __MAX__;

    function idxOf(name, kind) {
      for (var i = 0; i < schema.length; i++) {
        if (schema[i] && schema[i].name === name) return i;
      }
      var seen = 0;
      for (var j = 0; j < schema.length; j++) {
        var t = (schema[j] || {}).type;
        if (kind === "dim" && t === "dimension") return j;
        if (kind === "measure" && t === "measure") {
          if (seen === (name === NAMES.sessions ? 1 : 0)) return j;
          seen++;
        }
      }
      return -1;
    }
    var ui = idxOf(NAMES.user, "dim");
    var si = idxOf(NAMES.score, "measure");
    var ni = idxOf(NAMES.sessions, "measure");

    function tone(v) {
      return v >= 2.5 ? "#3DD9A0" : v >= 2.0 ? "#2BB8C9"
           : v >= 1.5 ? "#FFB712" : "#E0648C";
    }
    function person(email) {
      if (!email) return "";
      return String(email).split("@")[0].replace(/[._-]+/g, " ")
        .replace(/\\b[a-z]/g, function (m) { return m.toUpperCase(); });
    }

    var html = '<table class="lb"><thead><tr><th class="rank"></th><th>User</th>'
             + '<th class="score">Score</th><th class="num">Sessions</th>'
             + '</tr></thead><tbody>';
    rows.forEach(function (r, i) {
      var v = Number(r[si]);
      var pct = Math.max(0, Math.min(100, (v / MAX) * 100));
      html += '<tr><td class="rank">' + (i + 1) + '</td>'
        + '<td class="who" title="' + r[ui] + '">' + person(r[ui]) + '</td>'
        + '<td class="score"><div class="track"><div class="fill" style="width:'
        + pct.toFixed(1) + '%;background:' + tone(v) + '"></div></div>'
        + '<span class="val">' + (isFinite(v) ? v.toFixed(2) : "-") + '</span></td>'
        + '<td class="num">' + (ni >= 0 && r[ni] != null ? r[ni] : "") + '</td></tr>';
    });
    document.getElementById("chart").innerHTML = html + "</tbody></table>";
  } catch (e) {
    document.body.innerHTML = '<pre style="font:12px monospace;color:#BE123C">'
      + (e && e.message ? e.message : e) + "</pre>";
  }
})();
"""

CSS = """
html,body{margin:0;padding:0;font-family:'DM Sans',sans-serif;color:#191919}
#chart{width:100vw;height:100vh;overflow:auto;padding:4px 8px;box-sizing:border-box}
table.lb{width:100%;border-collapse:collapse;font-size:13px}
table.lb th{text-align:left;font-weight:500;font-size:11px;letter-spacing:.04em;
  text-transform:uppercase;color:#7F7E7C;padding:6px 8px;
  border-bottom:1px solid #E4E3DE;white-space:nowrap}
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
HTML = (
    '<div id="chart"></div>'
    '<div id="sink" style="position:absolute;left:-9999px;top:0;'
    'width:8px;height:8px;overflow:hidden"></div>'
)


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


def muze_chart(example_chart, names):
    chart = json.loads(json.dumps(example_chart))
    cols = [names["user"], names["score"], names["sessions"]]
    chart["type"] = "CUSTOM_CHART"
    chart["chart_columns"] = [{"column_id": c} for c in cols]
    chart["custom_chart_config"] = [
        {"key": "basic", "dimensions": [{"key": "fields", "columns": cols}]}
    ]
    js = JS_TEMPLATE.replace("__NAMES__", json.dumps(names)).replace(
        "__MAX__", str(MAX_SCORE)
    )
    chart["custom_visual_props"] = json.dumps(
        {
            "clientState": json.dumps(
                {
                    "version": 1,
                    "playground": {
                        "version": "v1",
                        "code": {
                            "jsCodeBase64": b64(js),
                            "cssCodeBase64": b64(CSS),
                            "htmlCodeBase64": b64(HTML),
                        },
                    },
                }
            )
        }
    )
    return chart


def main() -> None:
    target = LIVE if "--live" in sys.argv else COPY
    label = "LIVE" if target == LIVE else "COPY"
    tok = token()

    print(f"1. exporting {label} {target}")
    tml = export(target, tok)
    with open(SP / "backup" / f"liveboard_{target[:8]}_PRE_MUZE_ALL.json", "w") as fh:
        json.dump(tml, fh, indent=1)
    lb = tml["liveboard"]

    # a Muze chart block that ThoughtSpot itself produced, to clone from
    example = json.load((SP.parent / "references" / "muze_example_chart.json").open())[
        "answer"
    ]["chart"]

    # every tile whose name says leaderboard, excluding the variants testbed
    variant_tab = next(
        (t for t in lb["layout"]["tabs"] if t["name"] == "Leaderboard Variants"), None
    )
    skip = set()
    if variant_tab:
        skip = {t["visualization_id"] for t in variant_tab["tiles"]}

    targets = [
        v
        for v in lb["visualizations"]
        if "leaderboard" in ((v.get("answer") or {}).get("name") or "").lower()
        and v["id"] not in skip
    ]
    if not targets:
        raise SystemExit("ABORT: no leaderboard tiles found")

    converted = []
    for v in targets:
        answer = v["answer"]
        source = (answer.get("tables") or [{}])[0].get("name")
        if source not in SOURCE_COLUMNS:
            raise SystemExit(f"ABORT: {answer.get('name')} has unknown source {source!r}")
        score_tok, sessions_tok = SOURCE_COLUMNS[source]
        names = {
            "user": USER_COL,
            "score": f"Average {score_tok}",
            "sessions": f"Total {sessions_tok}",
        }

        filters = " ".join(FILTER_RE.findall(answer.get("search_query") or ""))
        answer["search_query"] = (
            f"[{USER_COL}] [{score_tok}] [{sessions_tok}] "
            f"{filters} sort by [{score_tok}] descending top 10"
        ).replace("  ", " ")
        answer["display_mode"] = "CHART_MODE"
        answer["chart"] = muze_chart(example, names)
        answer["answer_columns"] = [
            {"name": n} for n in (names["user"], names["score"], names["sessions"])
        ]
        answer.pop("table", None)
        converted.append((v["id"], answer["name"], source))
        print(f"   {answer['name'][:44]:<44} <- {source[:34]}")

    print(f"2. importing {len(converted)} converted tile(s)")
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

    print("3. verifying each kept its Muze payload and still returns rows")
    fresh = export(target, tok)["liveboard"]
    by_id = {v["id"]: v for v in fresh["visualizations"]}
    data = post(
        "/api/rest/2.0/metadata/liveboard/data", {"metadata_identifier": target}, tok
    )
    seen = {c["visualization_id"]: c for c in data.get("contents", [])}

    failed = False
    for viz_id, name, _ in converted:
        v = by_id.get(viz_id)
        if v is None:
            print(f"   BAD {name}: dropped on import")
            failed = True
            continue
        ch = v["answer"]["chart"]
        muze_ok = ch.get("type") == "CUSTOM_CHART" and bool(ch.get("custom_visual_props"))
        c = seen.get(v.get("viz_guid"))
        rows = 0 if c is None else len(c.get("data_rows", []))
        err = None if c is None else c.get("error")
        ok = muze_ok and rows > 0 and not err
        failed = failed or not ok
        print(
            f"   {'OK ' if ok else 'BAD'} {name[:44]:<44} muze={muze_ok} "
            f"rows={rows} err={err}"
        )

    print()
    if failed:
        print(f"FAILED — restore backup/liveboard_{target[:8]}_PRE_MUZE_ALL.json")
        raise SystemExit(1)
    print(f"VERIFIED on {label} — {len(converted)} leaderboard tiles now Muze tables.")


if __name__ == "__main__":
    main()
