import type { Theme } from '../theme.js'

// The input in the journal's form: a rounded frame around the prompt and the text, with the keys
// worth knowing in a dim row beneath it. The classic CLI draws the same frame (cli_tui_mixin.py).

/** Cells the frame takes from the input's row: the edge and a cell of air, on each side. */
export const COMPOSER_FRAME_COLS = 4

// Narrowest terminal that keeps a framed input usable.
const MIN_FRAMED_COLS = 40

/**
 * Whether the input sits in the frame. A skin that ships its own art keeps the bare input (the same
 * split the welcome page and the transcript rows make), as do a phone terminal and one too narrow
 * for the frame to leave room for text.
 */
export const composerFramed = (t: Theme, cols: number, termux = false): boolean =>
  !termux && cols >= MIN_FRAMED_COLS && !(t.bannerHero || t.bannerLogo)

/** The keys shown under the input, as `[key, what it does]`: the interrupt while a turn runs. */
export const composerKeyHints = (
  labels: { commands: string; help: string; interrupt: string },
  busy: boolean
): [string, string][] =>
  busy
    ? [
        ['Ctrl+C', labels.interrupt],
        ['/', labels.commands]
      ]
    : [
        ['/', labels.commands],
        ['?', labels.help]
      ]
