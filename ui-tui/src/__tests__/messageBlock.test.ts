import { PassThrough } from 'stream'

import { renderSync } from '@vael/ink'
import React from 'react'
import { describe, expect, it } from 'vitest'

import { MessageLine } from '../components/messageLine.js'
import { messageBlock } from '../domain/messageBlock.js'
import { DEFAULT_THEME } from '../theme.js'
import type { Msg } from '../types.js'

// A transcript row is a block in the journal's form: a bar down its left edge and a band behind
// the text — for the reader's messages and the agent's replies, and nothing else.

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

async function rows(msg: Msg, columns = 60): Promise<string[]> {
  const stdout = new PassThrough()
  const stdin = new PassThrough()
  const stderr = new PassThrough()

  Object.assign(stdout, { columns, isTTY: false, rows: 40 })
  Object.assign(stdin, { isTTY: false })
  Object.assign(stderr, { isTTY: false })

  let captured = ''
  stdout.on('data', chunk => {
    captured += chunk.toString()
  })

  const instance = renderSync(React.createElement(MessageLine, { cols: columns, msg, t: DEFAULT_THEME }), {
    patchConsole: false,
    stderr: stderr as NodeJS.WriteStream,
    stdin: stdin as NodeJS.ReadStream,
    stdout: stdout as NodeJS.WriteStream
  })

  try {
    await delay(20)

    // eslint-disable-next-line no-control-regex
    return captured.replace(/\u001b\[[0-9;]*m/g, '').split('\n')
  } finally {
    instance.unmount()
    instance.cleanup()
  }
}

describe('messageBlock', () => {
  it('is the reader and the agent only', () => {
    expect(messageBlock(DEFAULT_THEME, { role: 'user' })).not.toBeNull()
    expect(messageBlock(DEFAULT_THEME, { role: 'assistant' })).not.toBeNull()
    expect(messageBlock(DEFAULT_THEME, { role: 'system' })).toBeNull()
    expect(messageBlock(DEFAULT_THEME, { role: 'tool' })).toBeNull()
  })

  it('leaves events, diffs, slash echoes and the like as they were', () => {
    for (const kind of ['diff', 'event', 'intro', 'panel', 'slash', 'trail'] as const) {
      expect(messageBlock(DEFAULT_THEME, { kind, role: 'assistant' })).toBeNull()
      expect(messageBlock(DEFAULT_THEME, { kind, role: 'user' })).toBeNull()
    }
  })

  it('leaves every row of a skin that ships art as it was', () => {
    const withArt = { ...DEFAULT_THEME, bannerHero: '[#FF0000]ART[/]' }
    const withLogo = { ...DEFAULT_THEME, bannerLogo: '[#FF0000]LOGO[/]' }

    for (const t of [withArt, withLogo]) {
      expect(messageBlock(t, { role: 'user' })).toBeNull()
      expect(messageBlock(t, { role: 'assistant' })).toBeNull()
    }
  })

  it('keeps the prompt symbol a skin set on the reader rows, and only there', () => {
    const own = { ...DEFAULT_THEME, brand: { ...DEFAULT_THEME.brand, prompt: 'Ψ >' } }

    expect(messageBlock(DEFAULT_THEME, { role: 'user' })!.glyph).toBe(false)
    expect(messageBlock(own, { role: 'user' })!.glyph).toBe(true)
    expect(messageBlock(own, { role: 'assistant' })!.glyph).toBe(false)
  })

  it('tints the band apart from the bar, and the reader apart from the agent', () => {
    const user = messageBlock(DEFAULT_THEME, { role: 'user' })!
    const agent = messageBlock(DEFAULT_THEME, { role: 'assistant' })!

    expect(user.band).toMatch(/^#[0-9a-f]{6}$/i)
    expect(user.band).not.toBe(user.bar)
    expect(user.band).not.toBe(agent.band)
    expect(user.bar).not.toBe(agent.bar)
  })
})

describe('transcript rows', () => {
  it('carry the bar on every row of a long message, text included', async () => {
    const out = (await rows({ role: 'user', text: 'first line\nsecond line\nthird line' })).filter(l => l.trim())

    expect(out.length).toBeGreaterThanOrEqual(3)
    expect(out.every(l => l.startsWith('▌'))).toBe(true)
    expect(out.join('\n')).toContain('second line')
  })

  it('carry the bar on a reply that wraps', async () => {
    const out = (await rows({ role: 'assistant', text: 'word '.repeat(40).trim() }, 40)).filter(l => l.trim())

    expect(out.length).toBeGreaterThan(1)
    expect(out.every(l => l.startsWith('▌'))).toBe(true)
    expect(out.join(' ').match(/word/g)).toHaveLength(40)
  })

  it('leave a system note without a bar', async () => {
    const out = (await rows({ role: 'system', text: 'a note' })).join('\n')

    expect(out).toContain('a note')
    expect(out).not.toContain('▌')
  })
})
