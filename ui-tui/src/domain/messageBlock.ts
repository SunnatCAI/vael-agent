import { mix } from '@vael/shared/color'

import { DEFAULT_THEME, type Theme } from '../theme.js'
import type { Msg } from '../types.js'

// A transcript row in the journal's form: a bar down its left edge and a tinted band behind the
// text, instead of a glyph in the gutter. The same bar and band the classic CLI draws
// (vael_cli/journal.py::Journal.block), from the colours the status bar already uses.

/** A left edge that is only the bar: the other sides are switched off by the row's border flags. */
export const BAR_BORDER = {
  bottom: ' ',
  bottomLeft: ' ',
  bottomRight: ' ',
  left: '▌',
  right: ' ',
  top: ' ',
  topLeft: ' ',
  topRight: ' '
} as const

/** Cells between the bar and the text. */
export const BLOCK_GUTTER = 1

export interface MessageBlock {
  /** Tint behind the row's text. */
  band: string
  /** Colour of the bar. */
  bar: string
  /** The skin set its own prompt symbol, so the reader's rows keep it beside the text. */
  glyph: boolean
}

/**
 * The block a question that waits on the reader is drawn as — an approval, a confirmation — tinted
 * with the tone of the question (the warning colour, or the error colour for a dangerous one). A
 * skin that ships its own art keeps the framed box, as it does for the transcript.
 */
export function questionBlock(t: Theme, tone: string): MessageBlock | null {
  if (t.bannerHero || t.bannerLogo) {
    return null
  }

  return { band: mix(t.color.statusBg, tone, 0.12), bar: tone, glyph: false }
}

/**
 * The block a row is drawn as, or `null` for rows that stay as they were: system notes, tool
 * output, events, diffs, slash echoes — and every row of a skin that ships its own art, which keeps
 * its own look (the same split the welcome page makes). Only the reader's own messages and the
 * agent's replies are blocks.
 */
export function messageBlock(t: Theme, msg: Pick<Msg, 'kind' | 'role'>): MessageBlock | null {
  if (msg.kind || t.bannerHero || t.bannerLogo) {
    return null
  }

  if (msg.role === 'user') {
    return {
      band: mix(t.color.statusBg, t.color.accent, 0.12),
      bar: t.color.accent,
      glyph: t.brand.prompt !== DEFAULT_THEME.brand.prompt
    }
  }

  if (msg.role === 'assistant') {
    return { band: mix(t.color.statusBg, t.color.text, 0.06), bar: t.color.muted, glyph: false }
  }

  return null
}
