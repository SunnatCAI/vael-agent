---
version: 1
slug: "vael-cli-banner-py"
primary_target: "vael_cli/banner.py"
related_targets: ["vael_cli/skin_engine.py","vael_cli/cli_status_bar_mixin.py","ui-tui/src/theme.ts"]
---

# Console (classic CLI + TUI)

Mode: Operate. Scope: the terminal surfaces a person works in — welcome screen, transcript and tool
activity, approval prompt, status line — in the classic CLI (`vael_cli/`) and the Ink TUI (`ui-tui/`).
The desktop app is out of scope. Skins that ship their own hero art (ares, poseidon, sisyphus,
charizard, user YAML) keep the framed hero layout; every other skin gets the journal.

Audience and job: someone handing the agent a task. On opening they need: is it ready, where am I,
what can it do, what is it connected to, what waits for my approval.

Constraints: 80 columns up to very wide (content column capped at 100), dark and light terminals,
truecolor down to 16 colours, Windows Terminal / PowerShell first. English, Uzbek to follow through
the existing `agent.i18n` catalogue.

Chosen by the owner on 2026-10-12: direction "Journal", mark "the name on a green field".
Decision comp: https://claude.ai/artifact/RpX4GWGbX7CBGCNqy2az7u (section A).

## Direction contract

THESIS: the console is one continuous logbook page. Every line — header, inventory, question, tool
call, approval, answer — hangs off the same left margin, which carries its time and state. It refuses
the framed welcome panel with art beside a list, and the separate "chrome" above a chat.

OWN-WORLD: a nine-cell margin painted as a quiet green field; `HH:MM` and one state glyph in it
(`●` not ready, `▸` running, `✓` done, `?` waiting on you, `!` notice). An eleven-cell label column,
then the value, then a right-aligned figure or next command. Green `#18AA7F` (dark) / `#0A6B4F`
(light) for the mark, commands and good states; amber for anything that needs the person; neutrals
tinted toward green. Section labels are bold capitals. No frames, no art, no emoji, no faces.

STORY: the reader sees what blocks them and the command that clears it, then what the agent can
use, then what it is connected to. While it works they can read down the margin and know what ran,
when, and what is waiting on them.

FIRST VIEWPORT: row 1 `VAEL` on a green field in the margin, "VAEL Agent" and version, session at
the right edge. Row 3 the state line (`NOT READY` + reason, or the model and context size) with its
next commands. Then where / language, TOOLS grouped by purpose with counts at the right edge, SKILLS
as counted groups in three columns, LINKS, notices, the prompt in the margin, and a status line that
never shows a placeholder.

FORM: lab / engineering logbook — position 5 on the ordered list, seed key `aef3c501`.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Open

- Tool grouping by purpose (files / web / computer / memory / people) is new; toolset → group mapping
  lives in code and unknown toolsets fall into their own row.
- `/links`, `vael bridge link`, `vael sandbox setup` belong to the later bridge and sandbox work; the
  LINKS section shows only what exists today until they land.
- TUI parity, the four-outcome approval prompt and the Uzbek catalogue follow the classic CLI pass.
