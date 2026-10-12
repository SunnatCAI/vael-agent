import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'

import { afterEach, test, vi } from 'vitest'

import { platformDefaultVaelHome, resolveDesktopVaelHome, resolveDesktopUserData } from './data-paths'
import { controlSocketPath } from './ssh-connection'

afterEach((): void => {
  vi.unstubAllEnvs()
})

test.skipIf(process.platform === 'win32')('local SSH sockets use the suffixed default root', (): void => {
  vi.stubEnv('VAEL_DATA_DIR_SUFFIX', 'magic-test')
  const socket: string = controlSocketPath('user', 'host', 22)

  assert.equal(path.dirname(socket), path.join(platformDefaultVaelHome(os.homedir()), 'desktop-ssh'))
})

test('default data roots append the suffix literally on each platform', (): void => {
  for (const platform of ['linux', 'darwin', 'win32'] as const) {
    const paths: typeof path = platform === 'win32' ? path.win32 : path.posix
    const home: string = platform === 'win32' ? 'C:\\Users\\test' : '/home/test'
    const local: string = paths.join(home, 'AppData', 'Local')
    const userData: string = paths.join(home, 'app-data', 'VAEL')
    const base: string = platform === 'win32' ? paths.join(local, 'vael') : paths.join(home, '.vael')

    for (const suffix of ['', '-asdfasdf', 'magic-test', ' spaced ']) {
      const env: NodeJS.ProcessEnv = { LOCALAPPDATA: local, VAEL_DATA_DIR_SUFFIX: suffix }

      assert.equal(platformDefaultVaelHome(home, env, platform), base + suffix)
      assert.equal(resolveDesktopUserData(userData, env), userData + suffix)
      assert.equal(
        resolveDesktopVaelHome({ home, env, platform, directoryExists: (): boolean => false }),
        base + suffix
      )
    }
  }
})

test('explicit homes and userData retain precedence, and suffixed Windows homes never use legacy state', (): void => {
  const home: string = '/home/test'

  const env: NodeJS.ProcessEnv = {
    VAEL_DATA_DIR_SUFFIX: 'magic-test',
    VAEL_HOME: '/explicit/home',
    VAEL_DESKTOP_USER_DATA_DIR: '/explicit/electron'
  }

  assert.equal(resolveDesktopUserData('/default/electron', env), path.resolve(env.VAEL_DESKTOP_USER_DATA_DIR!))
  assert.equal(resolveDesktopVaelHome({ home, env, platform: 'linux' }), env.VAEL_HOME)
  delete env.VAEL_HOME
  assert.equal(resolveDesktopVaelHome({ home, env, platform: 'linux' }), '/explicit/electron/vael-home')

  const windowsHome: string = 'C:\\Users\\test'
  const windowsEnv: NodeJS.ProcessEnv = { VAEL_DATA_DIR_SUFFIX: 'magic-test' }
  const expected: string = path.win32.join(windowsHome, 'AppData', 'Local', 'vaelmagic-test')

  assert.equal(
    resolveDesktopVaelHome({
      home: windowsHome,
      env: windowsEnv,
      platform: 'win32',
      directoryExists: (): boolean => true
    }),
    expected
  )
  assert.equal(
    resolveDesktopVaelHome({
      home: windowsHome,
      env: windowsEnv,
      platform: 'win32',
      readWindowsHome: (): string => 'C:\\custom'
    }),
    'C:\\custom'
  )
})
