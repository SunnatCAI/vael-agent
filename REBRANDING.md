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

## Update source (owner decision, 2026-10-12)

`vael update` and the repository-based install paths use
`sunnatilla0717/vael-agent`: the official-remote set and fork detection
(`vael_cli/update_cmd_git.py`), the ZIP updater's default, the release
resolver's `OFFICIAL_REPOSITORY`, the installers' default clone URL, the
desktop bootstrap's raw script URL and the desktop app's publish target.
An install whose `origin` is that repository is no longer treated as a fork,
so the updater does not offer to add Hermes as `upstream`. The reinstall
hints printed by `vael update` and `vael uninstall`, and `scripts/install.cmd`,
use the installer scripts in that repository
(`raw.githubusercontent.com/sunnatilla0717/vael-agent/main/scripts/install.{sh,ps1}`).

Still upstream's, and so not usable for VAEL until it has its own: the
release-channel records host (`hermes-assets.nousresearch.com`; its records
name upstream's repository and are refused for this one, and only `main`
falls back to following the branch when no record exists), the hosted
installer one-liner where docs and the desktop app's remote-host hint still
show it (`hermes-agent.nousresearch.com/install.sh`, which installs Hermes)
and the Docker image name.

## What still says `hermes`, on purpose

- Upstream attribution: `LICENSE` is untouched (it carries Nous Research's
  copyright notice, which MIT requires keeping; it does not itself say
  "Hermes"), and credits that name the upstream project keep its name.
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

- The remaining `NousResearch/hermes-agent` repo references: docs and issue
  links, the official skills-hub source, release tooling, package metadata.
  (The updater is decided — see below.)
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
inventory (`rename-map.tsv`, `import-map.tsv`, …) and is kept verbatim.
`docs/verification-log.md` is the running log of the earlier phases (its last
entry is the wake-word rename) and is not rewritten by the rename tool.
`scripts/ir2-rollback.sh` reverses the file moves only; reverting the commit
is the real rollback.
