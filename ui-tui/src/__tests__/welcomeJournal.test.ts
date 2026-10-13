import { PassThrough } from 'stream'

import { renderSync } from '@vael/ink'
import React from 'react'
import { describe, expect, it } from 'vitest'

import { Banner, SessionPanel } from '../components/branding.js'
import { messages } from '../i18n/runtime.js'
import { DEFAULT_THEME, type Theme } from '../theme.js'
import type { SessionInfo } from '../types.js'

// The welcome page: the mark and wordmark, then the session's facts without a frame — unless the
// skin ships its own art, in which case it keeps the framed panel with the art beside the facts.

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

const info: SessionInfo = {
  cwd: 'D:/projects/cyberai',
  model: 'anthropic/claude-haiku-5-5',
  release_date: '2026.9.24',
  skills: { core: ['a', 'b'] },
  tools: { file: ['read_file', 'write_file'] },
  version: '1.2.3'
}

async function frame(element: React.ReactElement, columns: number): Promise<string> {
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

  const instance = renderSync(element, {
    patchConsole: false,
    stderr: stderr as NodeJS.WriteStream,
    stdin: stdin as NodeJS.ReadStream,
    stdout: stdout as NodeJS.WriteStream
  })

  try {
    await delay(20)

    // eslint-disable-next-line no-control-regex
    return captured.replace(/\u001b\[[0-9;]*m/g, '')
  } finally {
    instance.unmount()
    instance.cleanup()
  }
}

// Banner reads the real terminal's width; `maxWidth` narrows it, which is how a test sets one.
const banner = (columns: number, t: Theme = DEFAULT_THEME) =>
  frame(React.createElement(Banner, { maxWidth: columns, t }), columns)

const panel = (columns: number, t: Theme = DEFAULT_THEME) =>
  frame(React.createElement(SessionPanel, { info, sid: 'abc123', t }), columns)

const withHero: Theme = { ...DEFAULT_THEME, bannerHero: `[#FF0000]${'HEROART'.padEnd(40, '#')}[/]` }

describe('welcome page', () => {
  it('draws the mark and the wordmark, and never the company behind the upstream project', async () => {
    const out = await banner(80)

    expect(out).toContain('██╗   ██╗ █████╗ ███████╗██╗') // the wordmark
    expect(out).toContain('⢀⣴⡿⠛⢷⣤⡀') // the mark's first row
    expect(out).toContain(messages().chatBits.branding.tagFull)
    expect(out).not.toContain('Nous')
    expect(out).not.toContain('☤')
  })

  it('falls back to the name where the art does not fit', async () => {
    const out = await banner(48)

    expect(out).toContain('VAEL')
    expect(out).toContain(messages().chatBits.branding.tagMid)
    expect(out).not.toContain('█')
  })

  it('shows nothing where nothing fits', async () => {
    expect((await banner(30)).trim()).toBe('')
  })

  it('lists the session without a frame, name and model first', async () => {
    const out = await panel(120)

    expect(out).not.toMatch(/[╭╮╰╯]/)
    expect(out).toContain('VAEL Agent v1.2.3')
    expect(out).toContain('claude-haiku-5-5')
    expect(out.indexOf('VAEL Agent v1.2.3')).toBeLessThan(out.indexOf('claude-haiku-5-5'))
    expect(out).toContain('D:/projects/cyberai')
    expect(out).not.toContain('Nous')
  })

  it('keeps the framed panel and its art for a skin that ships art', async () => {
    const out = await panel(120, withHero)

    expect(out).toContain('╭')
    expect(out).toContain('HEROART')
    expect(out).toContain('claude-haiku-5-5')
    expect(out.indexOf('VAEL Agent v1.2.3')).toBeLessThan(out.indexOf('claude-haiku-5-5'))
    expect(out).not.toContain('Nous')
  })
})
