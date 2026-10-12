import assert from 'node:assert/strict'

import { test } from 'vitest'

import { hasWindowsPathPrefix, isExternalVenvHolder, isVaelOwnedVenvDaemon } from './venv-holder-select'

const SCRIPTS = 'C:\\VAEL\\venv\\Scripts'

test('matches the hindsight daemon shim (exe under venv Scripts + hindsight cmdline)', () => {
  assert.equal(
    isVaelOwnedVenvDaemon(
      'C:\\VAEL\\venv\\Scripts\\pythonw.exe',
      'C:\\VAEL\\venv\\Scripts\\pythonw.exe -m hindsight_api.main --daemon --idle-timeout 300 --port 9177',
      SCRIPTS
    ),
    true
  )
})

test('Windows path prefix match is ordinal case-insensitive', () => {
  assert.equal(
    isVaelOwnedVenvDaemon(
      'c:\\vael\\venv\\scripts\\python.exe',
      'python.exe -m hindsight_api.main --daemon',
      'C:\\VAEL\\venv\\Scripts'
    ),
    true
  )
})

test('excludes external venv holders that are not the hindsight daemon', () => {
  // a user terminal running the vael CLI from the venv — must NOT be killed
  assert.equal(isVaelOwnedVenvDaemon('C:\\VAEL\\venv\\Scripts\\vael.exe', 'vael chat -q "hi"', SCRIPTS), false)
  // an unrelated python script using the venv interpreter
  assert.equal(
    isVaelOwnedVenvDaemon('C:\\VAEL\\venv\\Scripts\\python.exe', 'python C:\\tools\\import.py', SCRIPTS),
    false
  )
})

test('excludes exes outside the venv even when the cmdline mentions hindsight', () => {
  assert.equal(
    isVaelOwnedVenvDaemon('C:\\Other\\pythonw.exe', 'pythonw -m hindsight_api.main --daemon', SCRIPTS),
    false
  )
})

test('prefix boundary: sibling dirs (ScriptsX) do not match', () => {
  assert.equal(hasWindowsPathPrefix('C:\\VAEL\\venv\\ScriptsX\\python.exe', SCRIPTS), false)
  assert.equal(hasWindowsPathPrefix('C:\\VAEL\\venv\\Scripts\\python.exe', SCRIPTS), true)
})

test('null/undefined fields never match', () => {
  assert.equal(isVaelOwnedVenvDaemon(null, 'x', SCRIPTS), false)
  assert.equal(isVaelOwnedVenvDaemon('C:\\VAEL\\venv\\Scripts\\pythonw.exe', null, SCRIPTS), false)
  assert.equal(isVaelOwnedVenvDaemon(undefined, undefined, SCRIPTS), false)
})

// --- isExternalVenvHolder (#62311) ------------------------------------------

test('matches the autostart gateway shim (vael.exe under venv Scripts)', () => {
  assert.equal(
    isExternalVenvHolder(
      'C:\\VAEL\\venv\\Scripts\\vael.exe',
      '"C:\\VAEL\\venv\\Scripts\\vael.exe" gateway run --external-supervisor',
      SCRIPTS
    ),
    true
  )
})

test('matches the dashboard scheduled task (python -m vael_cli / -m vael)', () => {
  assert.equal(
    isExternalVenvHolder(
      'C:\\VAEL\\venv\\Scripts\\python.exe',
      '"C:\\VAEL\\venv\\Scripts\\python.exe" -m vael_cli.main dashboard',
      SCRIPTS
    ),
    true
  )
  assert.equal(
    isExternalVenvHolder('C:\\VAEL\\venv\\Scripts\\pythonw.exe', 'pythonw.exe -m vael serve', SCRIPTS),
    true
  )
})

test('never matches an unrelated process that merely borrows the venv interpreter', () => {
  // a user's own script running on the venv python — NOT VAEL, must NOT be killed
  assert.equal(
    isExternalVenvHolder('C:\\VAEL\\venv\\Scripts\\python.exe', 'python C:\\tools\\import.py', SCRIPTS),
    false
  )
  // hindsight daemon is selected by isVaelOwnedVenvDaemon, not here
  assert.equal(
    isExternalVenvHolder('C:\\VAEL\\venv\\Scripts\\pythonw.exe', 'pythonw -m hindsight_api.main --daemon', SCRIPTS),
    false
  )
})

test('never matches a process outside the venv, even with vael in the cmdline', () => {
  // an editor / shell whose command line mentions the install root (#62445 regression guard)
  assert.equal(
    isExternalVenvHolder('C:\\Windows\\System32\\cmd.exe', 'cmd /c cd C:\\VAEL\\venv\\Scripts && dir', SCRIPTS),
    false
  )
  assert.equal(isExternalVenvHolder('C:\\Other\\vael.exe', 'vael gateway run', SCRIPTS), false)
})

test('sibling-dir and boundary safety for the external selector', () => {
  assert.equal(isExternalVenvHolder('C:\\VAEL\\venv\\ScriptsX\\vael.exe', 'vael gateway run', SCRIPTS), false)
  assert.equal(isExternalVenvHolder(null, 'vael gateway run', SCRIPTS), false)
  assert.equal(isExternalVenvHolder('C:\\VAEL\\venv\\Scripts\\vael.exe', null, SCRIPTS), false)
})
