#!/usr/bin/env python3
"""Restore a liveboard from a backup TML, then verify every tile returns rows.

The rollback half of the Muze workflow: re-imports a backup taken before the
Muze conversion and confirms zero CUSTOM_CHART tiles remain and every tile
still returns data. (Note: tiles that look blank right after a change are
usually just the multi-second Muze cold-load, not breakage -- browser-verify
with a 30-50s wait before deciding to revert.)

  python3 revert_muze.py <backup-filename> [--live]
"""

import json
import os
import pathlib
import sys
import urllib.request

SP = pathlib.Path(__file__).parent
TS = os.environ.get("THOUGHTSPOT_HOST", "https://YOUR-INSTANCE.thoughtspot.cloud")
COPY = os.environ.get("MUZE_COPY_GUID", "<copy-liveboard-guid>")
LIVE = os.environ.get("MUZE_LIVE_GUID", "<live-liveboard-guid>")


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


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    backup = SP / "backup" / sys.argv[1]
    target = LIVE if "--live" in sys.argv else COPY
    label = "LIVE" if target == LIVE else "COPY"
    tok = token()

    with open(backup) as fh:
        tml = json.load(fh)
    if tml.get("guid") != target:
        raise SystemExit(f"ABORT: backup is for {tml.get('guid')}, target is {target}")

    muze = sum(
        1
        for v in tml["liveboard"]["visualizations"]
        if ((v.get("answer") or {}).get("chart") or {}).get("type") == "CUSTOM_CHART"
    )
    print(f"1. restoring {label} from {backup.name} (contains {muze} custom-chart viz)")

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

    print("2. verifying no custom-chart tiles remain and every tile returns rows")
    fresh = export(target, tok)["liveboard"]
    left = [
        ((v.get("answer") or {}).get("name"))
        for v in fresh["visualizations"]
        if ((v.get("answer") or {}).get("chart") or {}).get("type") == "CUSTOM_CHART"
    ]
    print(f"   custom-chart tiles remaining: {len(left)} {left}")

    guids = {v["id"]: v.get("viz_guid") for v in fresh["visualizations"]}
    names = {
        v["id"]: (v.get("answer") or {}).get("name") for v in fresh["visualizations"]
    }
    queries = {
        v["id"]: (v.get("answer") or {}).get("search_query", "")
        for v in fresh["visualizations"]
    }
    data = post(
        "/api/rest/2.0/metadata/liveboard/data", {"metadata_identifier": target}, tok
    )
    seen = {c["visualization_id"]: c for c in data.get("contents", [])}

    total = bad = 0
    for tab in fresh["layout"]["tabs"]:
        ids = [t["visualization_id"] for t in tab["tiles"]]
        for g in tab.get("group_layouts", []):
            ids += [t["visualization_id"] for t in g["tiles"]]
        for i in ids:
            if not guids.get(i) or not queries.get(i):
                continue
            total += 1
            c = seen.get(guids[i])
            rows = (
                0
                if c is None
                else c.get("returned_data_row_count", len(c.get("data_rows", [])))
            )
            err = None if c is None else c.get("error")
            if not rows or err:
                bad += 1
                print(f"   BAD {tab['name']:<12} {names.get(i)} rows={rows} err={err}")
    print(f"\n   {total - bad}/{total} tiles returning rows")
    if bad or left:
        raise SystemExit("REVERT INCOMPLETE")
    print(f"REVERTED — {label} is back to the pre-Muze state.")


if __name__ == "__main__":
    main()
