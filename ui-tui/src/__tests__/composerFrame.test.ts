import { describe, expect, it } from 'vitest'

import { COMPOSER_FRAME_COLS, composerFramed, composerKeyHints } from '../lib/composerFrame.js'
import { DEFAULT_THEME } from '../theme.js'

const labels = { commands: 'commands', help: 'shortcuts', interrupt: 'interrupt' }

describe('composerFramed', () => {
  it('frames the input on an ordinary terminal', () => {
    expect(composerFramed(DEFAULT_THEME, 100)).toBe(true)
    expect(composerFramed(DEFAULT_THEME, 40)).toBe(true)
  })

  it('leaves a terminal too narrow for text beside the frame bare', () => {
    expect(composerFramed(DEFAULT_THEME, 39)).toBe(false)
    expect(100 - COMPOSER_FRAME_COLS).toBeGreaterThan(0)
  })

  it('leaves a phone terminal bare', () => {
    expect(composerFramed(DEFAULT_THEME, 100, true)).toBe(false)
  })

  it('leaves the input of a skin that ships art as it was', () => {
    expect(composerFramed({ ...DEFAULT_THEME, bannerHero: '[#FF0000]ART[/]' }, 100)).toBe(false)
    expect(composerFramed({ ...DEFAULT_THEME, bannerLogo: '[#FF0000]LOGO[/]' }, 100)).toBe(false)
  })
})

describe('composerKeyHints', () => {
  it('offers the commands and the shortcuts while idle', () => {
    expect(composerKeyHints(labels, false)).toEqual([
      ['/', 'commands'],
      ['?', 'shortcuts']
    ])
  })

  it('puts the interrupt first while a turn runs', () => {
    const hints = composerKeyHints(labels, true)

    expect(hints[0]).toEqual(['Ctrl+C', 'interrupt'])
    expect(hints.map(([key]) => key)).not.toContain('?')
  })
})
