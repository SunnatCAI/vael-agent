# VAEL console — design record

Derived from the shipped code (classic CLI in `vael_cli/`, TUI in `ui-tui/`), not from intentions.
Direction and brief: `PRODUCT.md`, `.impeccable/surfaces/vael-cli-banner-py.md`. Chosen by the owner on
2026-10-12 (layout "Journal", mark "the name on a green field"), extended on 2026-10-13 (large
wordmark, framed input, tinted message blocks, key hints).

## Thesis

The console is one continuous logbook page. Every row hangs off one left margin that carries its time and
state; the reader can read down that margin and know what ran, when, and what waits on them.

## Layout

| Part | Classic CLI | TUI |
|---|---|---|
| Margin | 9 cells: pad · `HH:MM` · space · state glyph · pad (`journal.GUTTER`) | none; rows start at the edge |
| Label column | 11 cells (`journal.LABEL`), grows to fit a longer label | accordion titles |
| Page width | content capped at 100 cells (`journal.MAX_WIDTH`) | terminal width |
| Message block | bar in the ninth cell (`BLOCK_INDENT = 8`), band as wide as the page | bar is the row's left border; text starts two cells in |

**State glyphs** (never colour alone; ASCII stand-ins `* > + ? ! x` when the console is ASCII-only):
`●` not ready · `▸` running · `✓` done · `?` waiting on you · `!` notice · `✗` failed.

## Surfaces

1. **Welcome.** The braille mark beside the VAEL wordmark, then name, version, model and place; then
   tools grouped by purpose, skills as counted groups, links, notices. Below 64 cells (classic) or 57
   (TUI) the name on the margin's green field (classic) or as text (TUI) stands in; the TUI shows no banner
   below 34 cells. In the TUI, journal-layout skins show the session facts frameless; a skin that ships
   `bannerHero` or `bannerLogo` keeps them framed.
2. **Message blocks.** A reply, your message and a question that waits on you are one form: a bar and a
   tinted band behind the text. Agent reply: dim bar, quiet band. Your message: accent bar, accent band,
   time at the right edge when timestamps are on. Question (approval, confirmation, clarify, sudo):
   warning bar and band (error colour for a dangerous one). In the classic CLI the first row carries the
   time and `?` in the margin; the TUI prompt has the bar and band but no timestamp margin.
3. **Tool rows.** One stamped row per finished call: verb and detail, duration (and failure reason) at
   the right edge.
4. **Input.** A rounded frame around prompt and text; the keys worth knowing in a dim row beneath
   (commands and shortcuts while idle, the interrupt first while a turn runs). Narrower than 40 cells,
   on a phone terminal (Termux), and for skins with art, the input stays bare.
5. **Status line.** Never shows a placeholder; carries the key hints at its right edge in the classic CLI
   when nothing else claims it.

## Colour

Tokens come from the skin, not from the components. Band colours are derived, not authored:
`mix(field, tone, 0.12)` for user and question blocks, `mix(field, text, 0.06)` for the agent's, where
`field` is the status bar's background (`status_bar_bg` / TUI `statusBg`).

| Role | Dark terminal | Light terminal |
|---|---|---|
| Brand / accent / good | `#18AA7F` (6.6:1 on black) | `#0A6B4F` (6.5:1 on white) |
| Field (margin, bands' base) | `#12211C` | `#E2F1EB` |
| Text | `#D3DCD7` | `#1B2420` |
| Dim | `#7C8B85` | `#5F6D67` |
| Needs the person (warn) | `#E0A83C` | `#8A5A06` |
| Error | `#EF6B5E` | `#B3261E` |
| Rule / frame | `#2E6F5B` | `#9CC7B8` |

`#18AA7F` is 2.9:1 on white, so on light terminals it never carries running text.

## Skins

A skin that ships its own art (`banner_hero` or `banner_logo`: ares, poseidon, sisyphus, charizard, user
YAML) keeps the framed hero layout, the framed response box, the double-framed question box and the bare
input. Every other skin gets the journal. The split is made in one place per surface:
`uses_journal_layout()` (classic), `framed` in `SessionPanel` / `messageBlock` / `questionBlock` /
`composerFramed` (TUI). Check both branches when changing either.

## Bans (owner)

No kawaii faces and no emoji as interface symbols; no `☤` caduceus (replaced by the name, and the bar in
the TUI); no "hacker film" imagery; no frames inside frames. The large wordmark is allowed by the owner's
2026-10-13 decision and overrides the earlier "no large ASCII art".

Still carrying faces or emoji as opt-in or legacy: the `kaomoji` and `emoji` busy-indicator styles (the
default is now the braille spinner), `cli.session.*` / `cli.commands.*` strings in `locales/en.yaml`
(`(^_^)`-style prefixes), the pet commands.

## Accessibility

- State is a glyph and a word, not colour alone; failures carry a reason in text.
- Bands are tints of the field, so text keeps the contrast it has on the field.
- Row text wraps inside the band; a long value continues under the value column and is never cut mid-name.
- Light and dark terminals, truecolor down to 16 colours (skins carry both palettes).

## Provenance

- **Braille mark** (`vael_cli/banner_journal.py::_MARK`, `ui-tui/src/banner.ts::MARK_ART`): traced from the
  owner's brand logo (`brand-logo.png`, kept in the CyberAI repo at `src/assets/brand-logo.png`: a green
  triangle with a four-point star) into braille, 19 × 8 cells: green pixels become dots, the image is cropped
  to the shape and each cell is lit at 45% coverage. The TUI copy is generated from the Python one.
- **Wordmark**: standard box-drawing block letters, no external source.
- No raster image ships in the console.

## Open

- A finish review against the contract on a real terminal (the TUI composer was only rendered in
  isolation; `npm run visual` needs Electron, which is not installed here).
- TUI skins other than the default: the art/no-art split is implemented but not looked at.
- `assets/nous-girl-*.svg` still carries the upstream project's art.
