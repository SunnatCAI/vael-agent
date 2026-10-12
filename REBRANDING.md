# REBRANDING.md

Hermes Agent → VAEL Agent rename. Status: the mechanical rename (the former
"IR2-B" phase) was applied in one scripted pass on 2026-10-12.

## Owner decisions (2026-10-12)

- **Everything internal is renamed, with no fallback.** `HERMES_*` → `VAEL_*`,
  `~/.hermes` → `~/.vael` (Windows: `%LOCALAPPDATA%\vael`), modules
  `hermes_*` → `vael_*`, npm scopes `@hermes/*` → `@vael/*`, deep-link scheme
  `hermes://` → `vael://`. Old names are not read; an existing Hermes home is
  migrated by hand.
- **The CLI is `vael` only** (`vael`, `vael-agent`, `vael-acp`). There is no
  `hermes` alias.
- Prose casing: `VAEL` as a word, `Vael` inside identifiers (`VaelCLI`),
  `vael` in lower-case names, `VAEL_` in constants.
- The 2026-10-04 KEEP decisions stand (below).

## What still says `hermes`, on purpose

- `LICENSE` and upstream attribution (MIT requires it).
- `contributors/emails/*`, `plugins/hermes-achievements/**` (vendored
  third-party), `plugin-catalog/*.yaml` (IDs are install keys) and every
  reference to a catalog plugin name, `openclaw_to_hermes.py`.
- `requires_hermes` — the plugin-manifest key the catalog files carry.
- Nous model names (`Hermes-4-405B`, `hermes-3-llama-3.1-70b`, `Hermes 3`,
  `--tool-call-parser hermes`), the few places code recognises that model
  family by the substring `hermes`, and third-party packages
  (`hermes-parser`, `hermes-estree`).
- The spoken wake phrase "hey hermes": the bundled model
  (`tools/wakewords/hey_vael.tflite`) was trained on it and fires on nothing
  else until it is regenerated (`docs/open-items.md`, P2).
- OAuth client IDs registered with third-party servers: Nous Portal
  (`hermes-cli`, `hermes-cli-vps`), Honcho (`hermes-agent`).
- Third-party project names and URLs (`HermesClaw`, `hermes-lcm`, …), and
  upstream issue numbers written as `hermes-agent#12345`.
- The legacy `⟪HERMES-CONTEXT-COMPRESSION:` marker prefix, in the dispatch
  guard only: sessions migrated from a Hermes home still replay it. New
  markers are minted with the VAEL prefix.

## Open: external identity still pointing upstream

These were left untouched because VAEL has no replacement for them yet. Each
needs an owner decision, not a mechanical edit:

- `NousResearch/hermes-agent` repo references, including the updater's
  source — `vael update` would pull upstream Hermes as written.
- `hermes-agent.nousresearch.com` install scripts, docs links and asset URLs.
- Docker images `nousresearch/hermes-agent`, `nousresearch/hermes-sandbox`.
- App identities. They are computed from the product name, so they now read
  `com.nousresearch.vael*`, `NousResearch.Vael*`, `chat.nous.vael` — the
  product half is renamed, the publisher half is still Nous Research's.
- Memory providers now default to `vael` where they defaulted to `hermes`,
  so memories stored under the old value need it set explicitly: Honcho
  `workspace` and `aiPeer` (and the `hosts.<name>` block in `honcho.json`),
  mem0 `agent_id`, Supermemory `container_tag`, RetainDB `agent_id`.
- Third-party skills and plugins written for Hermes (`metadata.hermes` in
  SKILL.md, `from hermes_cli …`, `@hermes/plugin-sdk`) are not recognised.
- Visual identity: the caduceus art and `☤`/`⚕` glyphs, icons, images.

Not re-verified after the rename: the Nix build (`package-lock.json` changed,
so any hash derived from it needs recomputing) and the Docker images.

## Historical mapping artifacts

[`docs/ir2-mapping/`](docs/ir2-mapping/summary.md) holds the pre-rename
inventory (`rename-map.tsv`, `import-map.tsv`, …) and is kept verbatim, as is
`docs/verification-log.md`. `scripts/ir2-rollback.sh` reverses the file moves
only; reverting the commit is the real rollback.
