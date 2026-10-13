# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Learners and practitioners in security, reached through the CyberAI platform (CTF console, AI mentor). Some are new to agents and need orientation.
- Developers at large, arriving from the open repository. They judge the product on its first run.
- The owner, who uses it daily and drives it remotely from a phone.

All of them arrive to hand the agent a task. On opening they need five answers: is it ready, where am I, what can it do, what is it connected to, what is waiting for my approval.

## Product Purpose

VAEL Agent is a personal AI agent that runs the same core in a terminal (classic CLI and a full-screen TUI), a messaging gateway (Telegram and others), and a desktop app. It uses tools on the user's own machine: terminal, files, browser, computer use, scheduled jobs. Success is a task finished without the user losing track of what the agent did or was allowed to do.

## Positioning

The agent works on the user's own computer with the user's own model keys, and can be driven from elsewhere (Telegram, CyberAI Flows) while every dangerous action stays behind an explicit grant.

## Operating Context

- Terminals from 80 columns to very wide, light and dark backgrounds, truecolor down to 16 colours. Windows Terminal and PowerShell are the owner's daily environment; Linux and macOS are equal targets.
- The classic CLI is Rich + prompt_toolkit (`vael_cli/banner.py`, `display.py`, status bar mixin). The TUI is Ink/React (`ui-tui/`). Colours come from the skin engine (`vael_cli/skin_engine.py`) and `ui-tui/src/theme.ts`, which are kept in step.
- CyberAI (`D:\CyberAI`) provides Flows, a pull-based PC Bridge and a Telegram bot. VAEL Agent is to become the bridge's executor.

## Capabilities and Constraints

- Interface languages: English by default; Uzbek (Latin) is bundled, with the other bundled languages.
- Approvals have four outcomes: always, this session, once, deny. A session grant ends with the session and is not restored on resume.
- Inside a sandbox the agent is not asked; outside it, dangerous actions are approved on the surface in use (the CLI prompt, or a messaging chat such as Telegram).
- Computer use has full access in a sandbox desktop; on the real screen it needs a grant each session.
- Open: what an "always" grant attaches to. Recommended and accepted in principle: a specific tool and command pattern, never a whole tool class.
- The desktop app is out of scope for the terminal redesign. Other skins (ares, mono, slate) stay.

## Brand Commitments

- Name: VAEL, written in capitals as a word.
- Primary colour `#18AA7F`. The former gold palette is retired in both light and dark.
- No kawaii faces and no emoji as interface symbols.
- No large ASCII art or block-letter logo; identity is a compact mark and the name.
- No "hacker film" imagery.
- No frames inside frames; structure comes from alignment and space.
- The `☤` glyph and the caduceus art belonged to Hermes and are to be replaced by a VAEL mark, still to be designed.

## Evidence on Hand

- The current first screen, captured by the owner at about 208 columns, and the code that draws it.
- No VAEL logo or mark exists yet. Do not present one as established.
- No published VAEL builds for desktop, MSIX, Termux or Docker.

## Product Principles

1. State before inventory: what blocks the user comes first, in plain words, with the next step.
2. Nothing truncated, nothing placeholder: show a thing fully or not at all.
3. Power stays visible: what the agent may do, and who granted it, is always answerable from the screen.
4. One system across CLI and TUI; a user moving between them should not relearn anything.
5. Legible to a newcomer, out of the way for an expert.

## Accessibility & Inclusion

- State is never carried by colour alone; every state has a word or a distinct glyph.
- Text must hold contrast on both light and dark terminals, and degrade cleanly without truecolor.
