// data-paths.mjs — the pure path-resolution core, shared by the desktop app
// (via data-paths.ts, a typed re-export) and the CI smoke driver (which runs
// under Node's type-stripping and therefore cannot import the app's
// extensionless TypeScript directly). No Electron imports here; only node:path.
//
// data-paths.ts re-exports these names and adds the TypeScript-facing
// `VaelHomeOptions` interface. Keep the two in lockstep: every behavior in
// this file is exercised by data-paths.test.ts through the re-export.

import path from 'node:path'

/** A VAEL_HOME rooted inside a `profiles/` directory names the profile's
 * parent (the home), not the profile directory itself. */
function normalizeVaelHomeRoot(vaelHome, pathModule) {
  if (!vaelHome) {
    return vaelHome
  }
  const resolved = pathModule.resolve(String(vaelHome))
  const parent = pathModule.dirname(resolved)
  if (pathModule.basename(parent).toLowerCase() === 'profiles') {
    return pathModule.dirname(parent)
  }
  return resolved
}

export function platformDefaultVaelHome(home, env = process.env, platform = process.platform) {
  const suffix = env.VAEL_DATA_DIR_SUFFIX || ''
  if (platform === 'win32') {
    const base = (env.LOCALAPPDATA || '').trim() || path.win32.join(home, 'AppData', 'Local')
    return path.win32.join(base, 'vael') + suffix
  }
  return path.posix.join(home, '.vael') + suffix
}

export function resolveDesktopUserData(defaultPath, env = process.env) {
  return env.VAEL_DESKTOP_USER_DATA_DIR
    ? path.resolve(env.VAEL_DESKTOP_USER_DATA_DIR)
    : defaultPath + (env.VAEL_DATA_DIR_SUFFIX || '')
}

export function resolveDesktopVaelHome({ home, env = process.env, platform = process.platform, directoryExists = () => false, readWindowsHome = () => null }) {
  const paths = platform === 'win32' ? path.win32 : path.posix
  if (env.VAEL_HOME) {
    return normalizeVaelHomeRoot(env.VAEL_HOME, paths)
  }
  // Fresh-install rehearsals must not touch the real VAEL home.
  if (env.VAEL_DESKTOP_USER_DATA_DIR) {
    return paths.join(paths.resolve(env.VAEL_DESKTOP_USER_DATA_DIR), 'vael-home')
  }
  if (platform === 'win32' && env.VAEL_HOME === undefined) {
    // Explorer can miss setx changes. An explicit empty value opts out of that fallback.
    const registryHome = readWindowsHome()
    if (registryHome) {
      return normalizeVaelHomeRoot(registryHome, paths)
    }
  }
  const defaultHome = platformDefaultVaelHome(home, env, platform)
  // Keep the legacy migration for ordinary installs, not isolated suffix runs.
  if (platform === 'win32' && !env.VAEL_DATA_DIR_SUFFIX) {
    const legacy = paths.join(home, '.vael')
    if (!directoryExists(defaultHome) && directoryExists(legacy)) {
      return legacy
    }
  }
  return defaultHome
}
