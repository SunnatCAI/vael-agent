# Open items

## IR2-A MANUAL-REVIEW decisions (owner, 2026-10-04) — applied to rename-map.tsv

- [x] `plugin-catalog/*.yaml` (66) → KEEP: third-party IDs are install keys.
- [x] `plugins/hermes-achievements/**` (9) → KEEP: keep vendored copy wrapped.
- [x] `openclaw_to_hermes.py` → KEEP: historical migration direction.
- [x] `tools/wakewords/hey_hermes.tflite` → renamed to `hey_vael.tflite`
  (`feat/wakeword-rename`); wake phrase stays `hey hermes` until the model
  is regenerated — see P2 below.
- [ ] TS alias renames (`@/hermes`, `@hermes/shared`, `@hermes/ink`) need
  tsconfig/vite/package.json updates + lockfile churn — verify with `tsc`.
- [ ] Symbol ripples (`HermesSkin`, `useHermesConfig`, `HermesConsoleModal`)
  need a content pass after the file moves.
- [ ] If IR2-B runs on the rebrand branch instead of main: the two
  `migrating-from-hermes.md` allowlist paths are KEEP there.

## origin/main vs local main (investigated 2026-10-04, decision pending)

`origin/main` (`4b7634b6`, 92 files, uploaded 2026-10-03 02:25) is an early
partial rebrand snapshot: 86 files byte-identical to local main, 2 identical
to the rebrand branch, 4 intermediate files fully superseded by the branch
(cli.py: 6 import lines only; hermes_constants.py: same 96-function R-7
design under the old filename; README/REBRANDING.md: older strings).
Zero unique work missing locally. Recommended: tag-backup
`4b7634b6`, then force-push local main (Option A) — needs explicit owner
confirmation; NEVER force-push without it. Until then, PRs against
origin/main show the whole history as new, and CI base-scope is wrong.

## Wake word model regeneration � P2, blocking-demo: no

- Reason: tools/wakewords/hey_vael.tflite is byte-identical to the old hey_hermes.tflite (SHA-256 744FDD81FEDC28FF1B9268BAEE20876CDF9BF1BC6F06BC2ED5C9CBEBC1A44B1D); only the filename changed. The weights still key the 'hey hermes' utterance, so users must still SAY 'hey hermes' � the 'hey vael' phrase does not trigger detection.
- Approach: train (or commission) a new openWakeWord-compatible .tflite for the 'hey vael' utterance, ship it alongside or replacing the current file, add 'hey vael' to _BUNDLED_MODEL_ALIASES + default phrase, update the loader comment and wake-word docs.
- Effort: needs audio training data + validation across engines (openwakeword/porcupine/sherpa); not a code-only change. Tracked here until then.

