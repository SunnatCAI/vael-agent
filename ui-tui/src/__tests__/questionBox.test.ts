import { PassThrough } from 'stream'

import { renderSync, Text } from '@vael/ink'
import React from 'react'
import { describe, expect, it } from 'vitest'

import { QuestionBox } from '../components/prompts.js'
import { questionBlock } from '../domain/messageBlock.js'
import { DEFAULT_THEME, type Theme } from '../theme.js'

// A question that waits on the reader — an approval, a confirmation — is a block: a bar down the
// left edge and a band behind the rows. A skin that ships its own art keeps the double frame.

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

async function rows(t: Theme): Promise<string[]> {
  const stdout = new PassThrough()
  const stdin = new PassThrough()
  const stderr = new PassThrough()

  Object.assign(stdout, { columns: 50, isTTY: false, rows: 20 })
  Object.assign(stdin, { isTTY: false })
  Object.assign(stderr, { isTTY: false })

  let captured = ''
  stdout.on('data', chunk => {
    captured += chunk.toString()
  })

  const element = React.createElement(
    QuestionBox,
    { t, tone: t.color.warn },
    React.createElement(Text, null, 'Approval needed'),
    React.createElement(Text, null, 'rm -rf build'),
    React.createElement(Text, null, '1. once')
  )

  const instance = renderSync(element, {
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

describe('questionBlock', () => {
  it('takes the tone of the question for the bar and a tint of it for the band', () => {
    const block = questionBlock(DEFAULT_THEME, DEFAULT_THEME.color.error)!

    expect(block.bar).toBe(DEFAULT_THEME.color.error)
    expect(block.band).toMatch(/^#[0-9a-f]{6}$/i)
    expect(block.band).not.toBe(block.bar)
    expect(questionBlock(DEFAULT_THEME, DEFAULT_THEME.color.warn)!.band).not.toBe(block.band)
  })

  it('is absent for a skin that ships art', () => {
    expect(questionBlock({ ...DEFAULT_THEME, bannerHero: '[#FF0000]ART[/]' }, '#E0A83C')).toBeNull()
    expect(questionBlock({ ...DEFAULT_THEME, bannerLogo: '[#FF0000]LOGO[/]' }, '#E0A83C')).toBeNull()
  })
})

describe('QuestionBox', () => {
  it('puts the bar in front of every row and draws no frame', async () => {
    const out = (await rows(DEFAULT_THEME)).filter(l => l.trim())

    expect(out).toHaveLength(3)
    expect(out.every(l => l.startsWith('▌'))).toBe(true)
    expect(out.join('\n')).toContain('rm -rf build')
    expect(out.join('')).not.toMatch(/[╔╗╚╝║═╭╮╰╯]/)
  })

  it('keeps the double frame for a skin that ships art', async () => {
    const out = (await rows({ ...DEFAULT_THEME, bannerHero: '[#FF0000]ART[/]' })).join('\n')

    expect(out).toContain('╔')
    expect(out).toContain('rm -rf build')
    expect(out).not.toContain('▌')
  })
})
