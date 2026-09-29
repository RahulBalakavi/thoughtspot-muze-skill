# thoughtspot-muze-skill

A [Claude Code](https://claude.com/claude-code) skill for building bespoke, on-brand ThoughtSpot liveboard tiles with **Muze** custom charts (`CUSTOM_CHART` vizzes carrying base64 JS/CSS/HTML), driven through the TML + REST API loop.

Companion to the AmpUp post [Embedded analytics with ThoughtSpot and Muze](https://www.ampup.ai/blog/embedded-analytics-thoughtspot-muze).

## Install

```bash
mkdir -p ~/.claude/skills
cp -r skills/thoughtspot-muze-dashboard ~/.claude/skills/
```

Then ask Claude for a "muze chart" or a custom-styled leaderboard on a liveboard.

## What's inside

- `SKILL.md`: workflow (clone a working chart block, build, copy-first verify, roll back), rendering paths, gotchas.
- `examples/`: `convert_tiles_to_muze.py` (canonical template), `add_new_muze_viz.py`, `revert_muze.py`.
- `references/`: Muze API snippets, renderer notes, a donor chart block.

Scripts read config from env vars: `THOUGHTSPOT_HOST`, `THOUGHTSPOT_USERNAME`, `THOUGHTSPOT_SECRET_KEY`, `MUZE_COPY_GUID`, `MUZE_LIVE_GUID`. The example view names, column tokens and GUIDs are placeholders to adapt to your worksheets.
