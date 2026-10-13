import type { ThemeColors } from './theme.js'

const RICH_RE = /\[(?:bold\s+)?(?:dim\s+)?(#(?:[0-9a-fA-F]{3,8}))\]([\s\S]*?)(\[\/\])/g

export function parseRichMarkup(markup: string): Line[] {
  const lines: Line[] = []

  for (const raw of markup.split('\n')) {
    const trimmed = raw.trimEnd()

    if (!trimmed) {
      lines.push(['', ' '])

      continue
    }

    const matches = [...trimmed.matchAll(RICH_RE)]

    if (!matches.length) {
      lines.push(['', trimmed])

      continue
    }

    let cursor = 0

    for (const m of matches) {
      const before = trimmed.slice(cursor, m.index)

      if (before) {
        lines.push(['', before])
      }

      lines.push([m[1]!, m[2]!])
      cursor = m.index! + m[0].length
    }

    if (cursor < trimmed.length) {
      lines.push(['', trimmed.slice(cursor)])
    }
  }

  return lines
}

// The mark traced from the logo into braille (19 cells wide) and the wordmark beside it, as the
// classic CLI's welcome page draws them. Kept in step with _MARK / _WORDMARK in
// vael_cli/banner_journal.py; the TUI draws them in one colour, row by row.
const MARK_ART = [
  '⠀⠀⠀⠀⠀⠀⢀⣴⡿⠛⢷⣤⡀⠀⠀⠀⠀⠀⠀',
  '⠀⠀⠀⠀⠀⢠⣾⣿⠁⠀⠈⣿⣷⡀⠀⠀⠀⠀⠀',
  '⠀⠀⠀⠀⢀⣿⣿⡇⠤⣿⠤⢸⣿⣷⡀⠀⠀⠀⠀',
  '⠀⠀⠀⢀⣾⣿⣿⡇⠀⠉⠀⢸⣿⣿⣷⡀⠀⠀⠀',
  '⠀⠀⢠⣾⣿⣿⣿⣿⣄⠀⣠⣿⣿⣿⣿⣷⡀⠀⠀',
  '⢀⣴⣿⣿⣿⣿⣿⢿⣫⣾⣿⣿⣿⣿⣿⣿⣿⣦⡀',
  '⠻⣿⢿⣛⣻⣿⣾⣿⣿⣿⣿⣿⣿⣿⣟⣛⡿⣿⣷',
  '⠻⣿⣿⣿⡿⠿⠛⠋⠁⠀⠈⠙⠛⠿⢿⣿⣿⣷⠛'
]

const WORDMARK_ART = [
  '',
  '██╗   ██╗ █████╗ ███████╗██╗     ',
  '██║   ██║██╔══██╗██╔════╝██║     ',
  '██║   ██║███████║█████╗  ██║     ',
  '╚██╗ ██╔╝██╔══██║██╔══╝  ██║     ',
  ' ╚████╔╝ ██║  ██║███████╗███████╗',
  '  ╚═══╝  ╚═╝  ╚═╝╚══════╝╚══════╝',
  ''
]

const LOGO_ART = MARK_ART.map((mark, i) => `${mark}   ${WORDMARK_ART[i] ?? ''}`.trimEnd())

export const LOGO_WIDTH = Math.max(...LOGO_ART.map(line => line.length))

export const logo = (c: ThemeColors, customLogo?: string): Line[] =>
  customLogo ? parseRichMarkup(customLogo) : LOGO_ART.map(text => [c.primary, text])

/** A skin's own hero art (`banner_hero`); the default welcome has none. */
export const skinHero = (customHero: string): Line[] => parseRichMarkup(customHero)

export const artWidth = (lines: Line[]) => lines.reduce((m, [, t]) => Math.max(m, t.length), 0)

type Line = [string, string]
