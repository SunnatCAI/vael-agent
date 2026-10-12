import { describe, expect, it } from 'vitest'

import {
  normalizeVaelOpenString,
  pathFromOpenDeepLink,
  pathFromVaelDeepLink,
  resolveVaelOpenPath
} from './vael-open-target'

describe('normalizeVaelOpenString', () => {
  it('accepts hash-router paths and strips a leading hash', () => {
    expect(normalizeVaelOpenString('/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeVaelOpenString('#/index-network/intent/1')).toBe('/index-network/intent/1')
  })

  it('maps plugin-scoped vael:// deep links to the same path', () => {
    expect(normalizeVaelOpenString('vael://index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeVaelOpenString('vael://index-network/intent/1?focus=true')).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('maps vael://open/… deep links by stripping the open host', () => {
    expect(normalizeVaelOpenString('vael://open/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeVaelOpenString('vael://open/settings/plugins')).toBe('/settings/plugins')
  })

  it('rejects reserved vael kinds and unsafe paths', () => {
    expect(normalizeVaelOpenString('vael://blueprint/morning-brief')).toBeNull()
    expect(normalizeVaelOpenString('vael://plugin/install')).toBeNull()
    expect(normalizeVaelOpenString('https://example.com/x')).toBeNull()
    expect(normalizeVaelOpenString('/../etc/passwd')).toBeNull()
    expect(normalizeVaelOpenString('index-network')).toBeNull()
  })
})

describe('resolveVaelOpenPath', () => {
  it('merges structured path + params', () => {
    expect(resolveVaelOpenPath({ path: '/index-network/intent/1', params: { focus: 'true' } })).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('resolves href the same as a bare string', () => {
    expect(resolveVaelOpenPath({ href: 'vael://index-network/intent/1' })).toBe('/index-network/intent/1')
  })
})

describe('pathFromVaelDeepLink', () => {
  it('builds the navigate path from a plugin-scoped deep-link payload', () => {
    expect(pathFromVaelDeepLink('index-network', 'intent/1')).toBe('/index-network/intent/1')
  })

  it('builds the navigate path from vael://open/… payloads', () => {
    expect(pathFromOpenDeepLink('index-network/intent/1')).toBe('/index-network/intent/1')
    expect(pathFromVaelDeepLink('open', 'agent/42')).toBe('/agent/42')
  })

  it('ignores reserved kinds', () => {
    expect(pathFromVaelDeepLink('blueprint', 'morning-brief')).toBeNull()
    expect(pathFromVaelDeepLink('plugin', 'install')).toBeNull()
    expect(pathFromVaelDeepLink('skill', 'install')).toBeNull()
  })
})
