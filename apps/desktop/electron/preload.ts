import { contextBridge, ipcRenderer, webFrame, webUtils } from 'electron'

import type { DesktopProfileRoute } from './desktop-profile'
import type { HudModifierApi, HudModifierStatus } from './hud-modifier-types'
import { customWindowControlsEnabled } from './window-controls'

// Which translucency the OS can back. Asked synchronously because the renderer
// needs it before its first paint, and answered by main because deciding it
// needs `os.release()` — a sandboxed preload may only require electron, events,
// timers and url, so importing node:os here throws before contextBridge runs
// and takes the ENTIRE bridge down with it (window.vaelDesktop undefined =>
// "Desktop IPC bridge is unavailable"). No reply means no glass, which degrades
// to an ordinary opaque window rather than a page thinned over nothing.
const translucencySupport = ipcRenderer.sendSync('vael:translucency:support')
const hudWindowing = ipcRenderer.sendSync('vael:hud:windowing')
const hudNativeDrag = hudWindowing?.nativeDrag === true

const launchFlags: { localModels?: boolean; guestOnboarding?: boolean } | undefined =
  ipcRenderer.sendSync('vael:feature-flags')

// Local, sanitized skin payload for the first renderer theme paint. This does
// not wait on `gateway.ready`, so an unreachable remote primary cannot force
// the built-in palette over the skin configured on this machine.
const localSkin = ipcRenderer.sendSync('vael:skin:local')

import { unwrapExpectedNotFound } from './api-expected-404'

contextBridge.exposeInMainWorld('vaelDesktop', {
  glassSupported: translucencySupport?.glass === true,
  translucencySupported: translucencySupport?.translucency === true,
  // Launch-flag fact: the app was started with --local, so the renderer may
  // show the local-models surfaces. Static for the window's lifetime.
  localModelsEnabled: launchFlags?.localModels === true,
  // Launch-flag fact: the Nous free tier is on for this launch
  // (VAEL_GUEST_ONBOARDING=1 or --guest-onboarding). Read-only; the same
  // decision is stamped onto every backend the app spawns.
  guestOnboardingEnabled: launchFlags?.guestOnboarding === true,
  localSkin: localSkin && typeof localSkin === 'object' ? localSkin : null,
  getConnection: (profile, opts) => ipcRenderer.invoke('vael:connection', profile, opts),
  // Loopback origin that hosts YouTube's player for the file:// renderer.
  getEmbedHostOrigin: () => ipcRenderer.invoke('vael:embed-host:origin'),
  // Registry-scoped backend resolution: { connectionId, profile } → descriptor.
  getConnectionFor: payload => ipcRenderer.invoke('vael:connection:for', payload),
  getProfileRoutes: profiles => ipcRenderer.invoke('vael:plugin-profile-routes', profiles),
  revalidateConnection: () => ipcRenderer.invoke('vael:connection:revalidate'),
  touchBackend: (profile, options) => ipcRenderer.invoke('vael:backend:touch', profile, options),
  getPoolLimits: () => ipcRenderer.invoke('vael:pool-limits:get'),
  setPoolLimits: limits => ipcRenderer.invoke('vael:pool-limits:set', limits),
  getGatewayWsUrl: profile => ipcRenderer.invoke('vael:gateway:ws-url', profile),
  // Registry-scoped fresh WS URL: { connectionId, profile } → result shape of
  // getGatewayWsUrl, minted against that connection's backend.
  getGatewayWsUrlFor: payload => ipcRenderer.invoke('vael:gateway:ws-url-for', payload),
  // Union agent roster across every registered connection.
  getAgentRoster: () => ipcRenderer.invoke('vael:agents:roster'),
  openSessionWindow: (sessionId, opts) => ipcRenderer.invoke('vael:window:openSession', sessionId, opts),
  openSessionInTerminal: (sessionId, opts) => ipcRenderer.invoke('vael:window:openInTerminal', sessionId, opts),
  openWindow: (options?: DesktopProfileRoute) => ipcRenderer.invoke('vael:window:openInstance', options),
  openBrowserWindow: tabId => ipcRenderer.invoke('vael:window:openBrowser', tabId),
  windowRelay: {
    send: payload => ipcRenderer.send('vael:window:relay', payload),
    onMessage: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('vael:window:relay', listener)

      return () => ipcRenderer.removeListener('vael:window:relay', listener)
    }
  },
  onBrowserPopoutClosed: callback => {
    const listener = (_event, tabId) => callback(tabId)
    ipcRenderer.on('vael:browser-popout:closed', listener)

    return () => ipcRenderer.removeListener('vael:browser-popout:closed', listener)
  },
  claimAmbientCue: key => ipcRenderer.invoke('vael:ambient:claim', key),
  windowControls: {
    custom: customWindowControlsEnabled(),
    minimize: () => ipcRenderer.send('vael:window-control', 'minimize'),
    toggleMaximize: () => ipcRenderer.send('vael:window-control', 'toggle-maximize'),
    close: () => ipcRenderer.send('vael:window-control', 'close')
  },
  wakeIndicator: {
    getState: () => ipcRenderer.invoke('vael:wake-indicator:get'),
    setState: state => ipcRenderer.send('vael:wake-indicator:set', state),
    onState: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('vael:wake-indicator:state', listener)

      return () => ipcRenderer.removeListener('vael:wake-indicator:state', listener)
    }
  },
  chatOnboarding: {
    grow: request => ipcRenderer.send('vael:chat-onboarding:grow', request),
    soloBoot: () => ipcRenderer.send('vael:chat-onboarding:solo-boot')
  },
  petOverlay: {
    // Main renderer → main process: window lifecycle + drag. `request` is
    // `{ bounds, screen }`; resolves with the screen bounds it actually used.
    open: request => ipcRenderer.invoke('vael:pet-overlay:open', request),
    close: () => ipcRenderer.invoke('vael:pet-overlay:close'),
    setBounds: bounds => ipcRenderer.send('vael:pet-overlay:set-bounds', bounds),
    setIgnoreMouse: ignore => ipcRenderer.send('vael:pet-overlay:ignore-mouse', ignore),
    // Flip the overlay focusable (and focus it) while the composer needs keys.
    setFocusable: focusable => ipcRenderer.send('vael:pet-overlay:set-focusable', focusable),
    // Main renderer → overlay (forwarded by main): push the latest pet state.
    pushState: payload => ipcRenderer.send('vael:pet-overlay:state', payload),
    // Overlay → main renderer (forwarded by main): pop back in / composer submit.
    control: payload => ipcRenderer.send('vael:pet-overlay:control', payload),
    // Overlay subscribes to state pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('vael:pet-overlay:state', listener)

      return () => ipcRenderer.removeListener('vael:pet-overlay:state', listener)
    },
    // Main renderer subscribes to overlay control messages.
    onControl: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('vael:pet-overlay:control', listener)

      return () => ipcRenderer.removeListener('vael:pet-overlay:control', listener)
    }
  },
  // HUD mode: the chrome-free floating chat. A full app renderer (own gateway)
  // sized as a floating bar, so it mounts the real composer. Main owns the
  // window; `onChanged` keeps every window's toggle truthful.
  hud: {
    nativeDrag: hudNativeDrag,
    windowing: {
      clientPlacement: hudWindowing?.clientPlacement !== false,
      controlDrag: hudWindowing?.controlDrag === true,
      nativeDrag: hudNativeDrag,
      solid: hudWindowing?.solid === true,
      workspaceTransfer: hudWindowing?.workspaceTransfer === true
    },
    open: request => ipcRenderer.invoke('vael:hud:open', request),
    close: () => ipcRenderer.invoke('vael:hud:close'),
    setIgnoreMouse: ignore => ipcRenderer.send('vael:hud:ignore-mouse', ignore),
    beginMove: () => ipcRenderer.send('vael:hud:begin-move'),
    endMove: () => ipcRenderer.send('vael:hud:end-move'),
    moveBy: delta => ipcRenderer.send('vael:hud:move-by', delta),
    setWorkspaceTransfer: transferring => ipcRenderer.send('vael:hud:workspace-transfer', transferring),
    setBounds: bounds => ipcRenderer.send('vael:hud:set-bounds', bounds),
    resetLayout: () => ipcRenderer.invoke('vael:hud:reset-layout'),
    // Whether the band covers the window below the bar. Main pairs it with the
    // user's translucency setting to decide the native frost (macOS vibrancy /
    // Windows 11 DWM backdrop) — see hudFrostFor.
    setFrost: showing => ipcRenderer.invoke('vael:hud:frost', showing),
    // The HUD tells main which session it is on; main hands that back to the
    // app window when the HUD closes, so the app can re-home onto it.
    setSession: sessionId => ipcRenderer.send('vael:hud:session', sessionId),
    onGoto: callback => {
      const listener = (_event, sessionId) => callback(sessionId)
      ipcRenderer.on('vael:hud:goto', listener)

      return () => ipcRenderer.removeListener('vael:hud:goto', listener)
    },
    onChanged: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('vael:hud:changed', listener)

      return () => ipcRenderer.removeListener('vael:hud:changed', listener)
    },
    // Linux only, and silent elsewhere: where the cursor is, in page
    // coordinates, or null when it has left the window. Stands in for the
    // mousemove that `setIgnoreMouseEvents(true, { forward: true })` delivers on
    // macOS and Windows but not here.
    onCursor: callback => {
      const listener = (_event, point) => callback(point)
      ipcRenderer.on('vael:hud:cursor', listener)

      return () => ipcRenderer.removeListener('vael:hud:cursor', listener)
    },
    // Main's game-overlay watch: whether a fullscreen app (a game) is under
    // the HUD, so the renderer can step back to the low-opacity overlay
    // treatment while one owns the screen.
    onGameOverlay: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('vael:hud:game-overlay', listener)

      return () => ipcRenderer.removeListener('vael:hud:game-overlay', listener)
    }
  },
  hudModifier: {
    getSettings: () => ipcRenderer.invoke('vael:hud-modifier:settings:get'),
    setEnabled: enabled => ipcRenderer.invoke('vael:hud-modifier:settings:set', enabled),
    openPermissionSettings: () => ipcRenderer.invoke('vael:hud-modifier:permission'),
    onStatus: callback => {
      const listener = (_event: Electron.IpcRendererEvent, status: HudModifierStatus) => callback(status)
      ipcRenderer.on('vael:hud-modifier:status', listener)

      return () => ipcRenderer.removeListener('vael:hud-modifier:status', listener)
    }
  } satisfies HudModifierApi,
  // macOS native screenshot gesture; captures require a main-issued request.
  screenshot:
    process.platform === 'darwin'
      ? {
          getSettings: () => ipcRenderer.invoke('vael:screenshot:settings:get'),
          setEnabled: enabled => ipcRenderer.invoke('vael:screenshot:settings:set', enabled),
          openPermissionSettings: kind => ipcRenderer.invoke('vael:screenshot:permission', kind),
          capture: requestId => ipcRenderer.invoke('vael:screenshot:capture', requestId),
          onStatus: callback => {
            const listener = (_event, status) => callback(status)
            ipcRenderer.on('vael:screenshot:status', listener)

            return () => ipcRenderer.removeListener('vael:screenshot:status', listener)
          },
          onRequest: callback => {
            const channel = 'vael:screenshot:request'
            const listener = (_event, requestId) => callback(requestId)

            if (ipcRenderer.listenerCount(channel) === 0) {
              ipcRenderer.send('vael:screenshot:subscribe', true)
            }

            ipcRenderer.on(channel, listener)

            return () => {
              ipcRenderer.removeListener(channel, listener)

              if (ipcRenderer.listenerCount(channel) === 0) {
                ipcRenderer.send('vael:screenshot:subscribe', false)
              }
            }
          }
        }
      : undefined,
  // Quick Entry: the global-hotkey mini composer window. Main owns the OS
  // shortcut + the persisted preference; the quick window only captures text
  // and hands it back, and the primary renderer submits it through the normal
  // prompt path.
  quickEntry: {
    getSettings: () => ipcRenderer.invoke('vael:quick-entry:settings:get'),
    setSettings: patch => ipcRenderer.invoke('vael:quick-entry:settings:set', patch),
    // Invoke returns the delivery result so the draft is not lost (#85590).
    submit: payload => ipcRenderer.invoke('vael:quick-entry:submit', payload),
    // Main cannot invoke the primary renderer, so it receives this ack (#85590).
    ackSubmit: (correlationId, result) => ipcRenderer.send('vael:quick-entry:ack', { correlationId, result }),
    dismiss: () => ipcRenderer.send('vael:quick-entry:dismiss'),
    // Primary renderer → main → quick window: gateway connection state + the
    // recent-session options the target picker offers. Main caches the latest
    // payload so a freshly spawned quick window starts from truth.
    pushState: payload => ipcRenderer.send('vael:quick-entry:state', payload),
    // Quick window subscribes to those pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('vael:quick-entry:state', listener)

      return () => ipcRenderer.removeListener('vael:quick-entry:state', listener)
    },
    // Main → primary renderer: a submit captured by the quick window.
    onSubmit: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('vael:quick-entry:submit', listener)

      return () => ipcRenderer.removeListener('vael:quick-entry:submit', listener)
    },
    // Main → quick window: you were just summoned (reset draft + refocus).
    onShown: callback => {
      const listener = () => callback()
      ipcRenderer.on('vael:quick-entry:shown', listener)

      return () => ipcRenderer.removeListener('vael:quick-entry:shown', listener)
    },
    // Main → quick window: the outcome of a submit whose relay already timed
    // out. Delivery is now KNOWN — reconcile the unknown state instead of
    // leaving the user to resend a prompt that may already be delivered.
    onLateResult: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('vael:quick-entry:late-result', listener)

      return () => ipcRenderer.removeListener('vael:quick-entry:late-result', listener)
    }
  },
  getBootProgress: () => ipcRenderer.invoke('vael:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('vael:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('vael:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('vael:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('vael:connection-config:test', payload),
  // Opt-in OS-keychain encryption for stored gateway secrets (default off —
  // see secret-storage-policy.ts). get never touches the OS keychain.
  getSecretStorageEncryption: () => ipcRenderer.invoke('vael:secret-storage:get'),
  setSecretStorageEncryption: (on: boolean) => ipcRenderer.invoke('vael:secret-storage:set', on),
  // v2 multi-connection registry: named agent sources (local / remote / cloud / ssh).
  connections: {
    list: () => ipcRenderer.invoke('vael:connections:list'),
    save: payload => ipcRenderer.invoke('vael:connections:save', payload),
    remove: id => ipcRenderer.invoke('vael:connections:remove', id),
    setPrimary: id => ipcRenderer.invoke('vael:connections:set-primary', id),
    setLaunchMode: mode => ipcRenderer.invoke('vael:connections:set-launch-mode', mode),
    setLastUsed: id => ipcRenderer.invoke('vael:connections:set-last-used', id),
    test: id => ipcRenderer.invoke('vael:connections:test', id),
    updateManaged: id => ipcRenderer.invoke('vael:connections:update-managed', id),
    // Fan out `vael update` to every eligible registered connection.
    // Optional excludeIds skips rows the caller updates through another path.
    updateAll: options => ipcRenderer.invoke('vael:connections:update-all', options),
    // Registry lifecycle push (main → renderer): a connection was removed or
    // materially edited, so secondaries scoped to it must be disposed (and,
    // for edits, re-dialed at the new target).
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('vael:connections:changed', listener)

      return () => ipcRenderer.removeListener('vael:connections:changed', listener)
    }
  },
  sshConfigHosts: () => ipcRenderer.invoke('vael:ssh-config:hosts'),
  sshResolveHost: host => ipcRenderer.invoke('vael:ssh-config:resolve', host),
  probeConnectionConfig: remoteUrl => ipcRenderer.invoke('vael:connection-config:probe', remoteUrl),
  // `options` lets a registry-editor draft sign in BEFORE it is saved: the
  // main process settles the draft's connection id up front so the login
  // window writes into the per-connection cookie jar the saved entry will
  // read (not the legacy shared jar an unsaved URL would fall back to).
  oauthLoginConnectionConfig: (remoteUrl, options) =>
    ipcRenderer.invoke('vael:connection-config:oauth-login', remoteUrl, options),
  oauthLogoutConnectionConfig: remoteUrl => ipcRenderer.invoke('vael:connection-config:oauth-logout', remoteUrl),
  // VAEL Cloud: one portal login powers discovery + silent per-agent sign-in
  // (cloud-auto-discovery Phase 3).
  cloud: {
    status: () => ipcRenderer.invoke('vael:cloud:status'),
    login: () => ipcRenderer.invoke('vael:cloud:login'),
    logout: () => ipcRenderer.invoke('vael:cloud:logout'),
    discover: org => ipcRenderer.invoke('vael:cloud:discover', org),
    agentSignIn: dashboardUrl => ipcRenderer.invoke('vael:cloud:agent-sign-in', dashboardUrl)
  },
  profile: {
    getDefault: () => ipcRenderer.invoke('vael:profile:default:get'),
    setDefault: (route: DesktopProfileRoute) => ipcRenderer.invoke('vael:profile:default:set', route),
    onDefaultChanged: (callback: (route: DesktopProfileRoute | null) => void) => {
      const listener = (_event: Electron.IpcRendererEvent, route: DesktopProfileRoute | null) => callback(route)
      ipcRenderer.on('vael:profile:default:changed', listener)

      return () => ipcRenderer.removeListener('vael:profile:default:changed', listener)
    },
    get: () => ipcRenderer.invoke('vael:profile:get'),
    remember: name => ipcRenderer.invoke('vael:profile:remember', name),
    set: name => ipcRenderer.invoke('vael:profile:set', name)
  },
  // The handler resolves an expected 404 with a sentinel instead of rejecting
  // (Electron logs a stack for every rejected invoke). Turn it back into the
  // rejection the renderer expects — see electron/api-expected-404.ts.
  api: request => ipcRenderer.invoke('vael:api', request).then(unwrapExpectedNotFound),
  notify: payload => ipcRenderer.invoke('vael:notify', payload),
  claimStartupLatency: () => ipcRenderer.invoke('vael:startup-latency:claim'),
  requestMicrophoneAccess: () => ipcRenderer.invoke('vael:requestMicrophoneAccess'),
  readWindowBelow: () => ipcRenderer.invoke('vael:window:readBelow'),
  readFileDataUrl: filePath => ipcRenderer.invoke('vael:readFileDataUrl', filePath),
  readFileDataUrlForAttach: filePath => ipcRenderer.invoke('vael:readFileDataUrlForAttach', filePath),
  dataUrlReadMax: {
    get: () => ipcRenderer.invoke('vael:data-url-read-max:get'),
    set: maxMb => ipcRenderer.invoke('vael:data-url-read-max:set', maxMb)
  },
  readFileText: filePath => ipcRenderer.invoke('vael:readFileText', filePath),
  readPluginSource: (filePath: string) => ipcRenderer.invoke('vael:readPluginSource', filePath),
  selectPaths: options => ipcRenderer.invoke('vael:selectPaths', options),
  selectSavePath: options => ipcRenderer.invoke('vael:selectSavePath', options),
  writeClipboard: text => ipcRenderer.invoke('vael:writeClipboard', text),
  readClipboard: () => ipcRenderer.invoke('vael:readClipboard'),
  saveGatewayFile: payload => ipcRenderer.invoke('vael:saveGatewayFile', payload),
  saveImageFromUrl: url => ipcRenderer.invoke('vael:saveImageFromUrl', url),
  contextMenuEdit: command => ipcRenderer.invoke('vael:context-menu:edit', command),
  contextMenuCopyImage: () => ipcRenderer.invoke('vael:context-menu:copy-image'),
  contextMenuSpellcheck: action => ipcRenderer.invoke('vael:context-menu:spellcheck', action),
  contextMenuGuestAddWord: payload => ipcRenderer.invoke('vael:context-menu:guest-add-word', payload),
  onContextMenuSpellcheck: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('vael:context-menu-spellcheck', listener)

    return () => ipcRenderer.removeListener('vael:context-menu-spellcheck', listener)
  },
  saveImageBuffer: (data, ext, name) => ipcRenderer.invoke('vael:saveImageBuffer', { data, ext, name }),
  capturePreview: payload => ipcRenderer.invoke('vael:capturePreview', payload),
  savePastedText: text => ipcRenderer.invoke('vael:savePastedText', { text }),
  saveClipboardImage: () => ipcRenderer.invoke('vael:saveClipboardImage'),
  getPathForFile: file => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return ''
    }
  },
  normalizePreviewTarget: (target, baseDir) => ipcRenderer.invoke('vael:normalizePreviewTarget', target, baseDir),
  watchPreviewFile: url => ipcRenderer.invoke('vael:watchPreviewFile', url),
  watchDirectory: dir => ipcRenderer.invoke('vael:watchDirectory', dir),
  stopPreviewFileWatch: id => ipcRenderer.invoke('vael:stopPreviewFileWatch', id),
  setActiveWork: payload => ipcRenderer.send('vael:active-work', payload),
  setTitleBarTheme: payload => ipcRenderer.send('vael:titlebar-theme', payload),
  setNativeTheme: mode => ipcRenderer.send('vael:native-theme', mode),
  setTranslucency: payload => ipcRenderer.send('vael:translucency', payload),
  setKeepAwake: on => ipcRenderer.send('vael:keep-awake', on),
  minimizeToTray: {
    get: () => ipcRenderer.invoke('vael:minimize-to-tray:get'),
    set: on => ipcRenderer.invoke('vael:minimize-to-tray:set', on),
    onChanged: callback => {
      const listener = (_event, status) => callback(status)
      ipcRenderer.on('vael:minimize-to-tray:changed', listener)

      return () => ipcRenderer.removeListener('vael:minimize-to-tray:changed', listener)
    }
  },
  setDisableF12: blocked => ipcRenderer.send('vael:devtools:disable-f12', blocked),
  setF12ShortcutActive: active => ipcRenderer.send('vael:f12ShortcutActive', Boolean(active)),
  onF12Shortcut: callback => {
    const listener = (_event, input) => callback(input)
    ipcRenderer.on('vael:f12-shortcut', listener)

    return () => ipcRenderer.removeListener('vael:f12-shortcut', listener)
  },
  setPreviewShortcutActive: active => ipcRenderer.send('vael:previewShortcutActive', Boolean(active)),
  openExternal: url => ipcRenderer.invoke('vael:openExternal', url),
  mcpOauth: {
    // One-shot loopback listener for MCP OAuth against remote backends: bind
    // on this machine, hand redirectUri to mcp.servers.oauth.start, then wait
    // for the provider redirect and relay code/state via oauth.callback.
    listen: () => ipcRenderer.invoke('vael:mcp-oauth:listen'),
    wait: (id, timeoutMs) => ipcRenderer.invoke('vael:mcp-oauth:wait', id, timeoutMs),
    cancel: id => ipcRenderer.invoke('vael:mcp-oauth:cancel', id)
  },
  openPreviewInBrowser: url => ipcRenderer.invoke('vael:openPreviewInBrowser', url),
  reachPreviewUrl: url => ipcRenderer.invoke('vael:preview:reach', url),
  setActiveConnectionRoute: route => ipcRenderer.send('vael:connection:active-route', route),
  fetchLinkTitle: url => ipcRenderer.invoke('vael:fetchLinkTitle', url),
  resolveFavicon: url => ipcRenderer.invoke('vael:resolveFavicon', url),
  sanitizeWorkspaceCwd: cwd => ipcRenderer.invoke('vael:workspace:sanitize', cwd),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('vael:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('vael:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('vael:setting:defaultProjectDir:pick')
  },
  zoom: {
    // Current zoom of this window, as { level, percent }.
    get: () => ipcRenderer.invoke('vael:zoom:get'),
    // Synchronous zoom factor (1 = 100%). Coordinate math needs it in the
    // same tick as the event it converts, so no IPC round-trip here.
    factor: () => webFrame.getZoomFactor(),
    setPercent: percent => ipcRenderer.send('vael:zoom:set-percent', percent),
    // Fires on every zoom change, including the Ctrl/Cmd +/-/0 shortcuts,
    // so the settings UI can stay in sync with the keyboard.
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('vael:zoom:changed', listener)

      return () => ipcRenderer.removeListener('vael:zoom:changed', listener)
    }
  },
  revealLogs: () => ipcRenderer.invoke('vael:logs:reveal'),
  getRecentLogs: () => ipcRenderer.invoke('vael:logs:recent'),
  // Fire-and-forget: persists a renderer error-boundary catch (with component
  // stack) to desktop.log so crashes survive the window (#79428).
  reportRendererError: report => ipcRenderer.send('vael:logs:renderer-error', report),
  logLine: (line: string): void => ipcRenderer.send('vael:logs:renderer-line', line),
  readDir: dirPath => ipcRenderer.invoke('vael:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('vael:fs:gitRoot', startPath),
  revealPath: targetPath => ipcRenderer.invoke('vael:fs:reveal', targetPath),
  openDir: dirPath => ipcRenderer.invoke('vael:fs:openDir', dirPath),
  desktopPluginsRoot: () => ipcRenderer.invoke('vael:fs:desktopPluginsRoot'),
  reconcileDesktopPlugins: () => ipcRenderer.invoke('vael:fs:reconcileDesktopPlugins'),
  logsRoot: (profile?: string) => ipcRenderer.invoke('vael:fs:logsRoot', profile),
  renamePath: (targetPath, newName) => ipcRenderer.invoke('vael:fs:rename', targetPath, newName),
  writeTextFile: (filePath, content) => ipcRenderer.invoke('vael:fs:writeText', filePath, content),
  trashPath: targetPath => ipcRenderer.invoke('vael:fs:trash', targetPath),
  git: {
    worktreeList: repoPath => ipcRenderer.invoke('vael:git:worktreeList', repoPath),
    worktreeAdd: (repoPath, options) => ipcRenderer.invoke('vael:git:worktreeAdd', repoPath, options),
    worktreeRemove: (repoPath, worktreePath, options) =>
      ipcRenderer.invoke('vael:git:worktreeRemove', repoPath, worktreePath, options),
    branchSwitch: (repoPath, branch) => ipcRenderer.invoke('vael:git:branchSwitch', repoPath, branch),
    branchList: repoPath => ipcRenderer.invoke('vael:git:branchList', repoPath),
    baseBranchList: repoPath => ipcRenderer.invoke('vael:git:baseBranchList', repoPath),
    repoStatus: repoPath => ipcRenderer.invoke('vael:git:repoStatus', repoPath),
    fileDiff: (repoPath, filePath) => ipcRenderer.invoke('vael:git:fileDiff', repoPath, filePath),
    scanRepos: (roots, options) => ipcRenderer.invoke('vael:git:scanRepos', roots, options),
    review: {
      list: (repoPath, scope, baseRef) => ipcRenderer.invoke('vael:git:review:list', repoPath, scope, baseRef),
      diff: (repoPath, filePath, scope, baseRef, staged) =>
        ipcRenderer.invoke('vael:git:review:diff', repoPath, filePath, scope, baseRef, staged),
      stage: (repoPath, filePath) => ipcRenderer.invoke('vael:git:review:stage', repoPath, filePath),
      unstage: (repoPath, filePath) => ipcRenderer.invoke('vael:git:review:unstage', repoPath, filePath),
      revert: (repoPath, filePath) => ipcRenderer.invoke('vael:git:review:revert', repoPath, filePath),
      revParse: (repoPath, ref) => ipcRenderer.invoke('vael:git:review:revParse', repoPath, ref),
      commit: (repoPath, message, push) => ipcRenderer.invoke('vael:git:review:commit', repoPath, message, push),
      commitContext: repoPath => ipcRenderer.invoke('vael:git:review:commitContext', repoPath),
      push: repoPath => ipcRenderer.invoke('vael:git:review:push', repoPath),
      shipInfo: repoPath => ipcRenderer.invoke('vael:git:review:shipInfo', repoPath),
      prList: (repoPath, branches, numbers) =>
        ipcRenderer.invoke('vael:git:review:prList', repoPath, branches, numbers),
      createPr: repoPath => ipcRenderer.invoke('vael:git:review:createPr', repoPath)
    }
  },
  terminal: {
    attach: id => ipcRenderer.invoke('vael:terminal:attach', id),
    cwd: id => ipcRenderer.invoke('vael:terminal:cwd', id),
    dispose: id => ipcRenderer.invoke('vael:terminal:dispose', id),
    resize: (id, size) => ipcRenderer.invoke('vael:terminal:resize', id, size),
    start: options => ipcRenderer.invoke('vael:terminal:start', options),
    write: (id, data) => ipcRenderer.invoke('vael:terminal:write', id, data),
    onData: (id, callback) => {
      const channel = `vael:terminal:${id}:data`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (id, callback) => {
      const channel = `vael:terminal:${id}:exit`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    }
  },
  onClosePreviewRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('vael:close-preview-requested', listener)

    return () => ipcRenderer.removeListener('vael:close-preview-requested', listener)
  },
  onPreviewNav: callback => {
    const listener = (_event, command) => callback(command)
    ipcRenderer.on('vael:preview-nav', listener)

    return () => ipcRenderer.removeListener('vael:preview-nav', listener)
  },
  onOpenFolderRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('vael:open-folder-requested', listener)

    return () => ipcRenderer.removeListener('vael:open-folder-requested', listener)
  },
  onOpenUpdatesRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('vael:open-updates', listener)

    return () => ipcRenderer.removeListener('vael:open-updates', listener)
  },
  onDeepLink: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('vael:deep-link', listener)

    return () => ipcRenderer.removeListener('vael:deep-link', listener)
  },
  signalDeepLinkReady: () => ipcRenderer.invoke('vael:deep-link-ready'),
  probePluginRepo: payload => ipcRenderer.invoke('vael:plugin:probe', payload),
  installDesktopPlugin: payload => ipcRenderer.invoke('vael:plugin:installDesktop', payload),
  removeDesktopPlugin: payload => ipcRenderer.invoke('vael:plugin:removeDesktop', payload),
  onWindowStateChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('vael:window-state-changed', listener)

    return () => ipcRenderer.removeListener('vael:window-state-changed', listener)
  },
  onFocusSession: callback => {
    const listener = (_event, sessionId) => callback(sessionId)
    ipcRenderer.on('vael:focus-session', listener)

    return () => ipcRenderer.removeListener('vael:focus-session', listener)
  },
  onNotificationAction: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('vael:notification-action', listener)

    return () => ipcRenderer.removeListener('vael:notification-action', listener)
  },
  onNotificationActivate: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('vael:notification-activate', listener)

    return () => ipcRenderer.removeListener('vael:notification-activate', listener)
  },
  onExternalOpenFailed: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('vael:external-open-failed', listener)

    return () => ipcRenderer.removeListener('vael:external-open-failed', listener)
  },
  onPreviewFileChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('vael:preview-file-changed', listener)

    return () => ipcRenderer.removeListener('vael:preview-file-changed', listener)
  },
  onBackendExit: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('vael:backend-exit', listener)

    return () => ipcRenderer.removeListener('vael:backend-exit', listener)
  },
  // Cooperative pool retirement (main → renderer): the pooled backend under
  // `poolKey` is being stopped for a foreground open. Park that scope; do not
  // redial into the slot it vacated.
  onPoolBackendRetiring: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('vael:pool:retiring', listener)

    return () => ipcRenderer.removeListener('vael:pool:retiring', listener)
  },
  // Soft gateway-mode apply finished tearing down the primary backend. Renderer
  // should wipe session lists + re-dial without a window reload.
  onConnectionApplied: callback => {
    const listener = () => callback()
    ipcRenderer.on('vael:connection:applied', listener)

    return () => ipcRenderer.removeListener('vael:connection:applied', listener)
  },
  onPowerResume: callback => {
    const listener = () => callback()
    ipcRenderer.on('vael:power-resume', listener)

    return () => ipcRenderer.removeListener('vael:power-resume', listener)
  },
  // AC ↔ battery transitions; renderers slow their backstop polls on battery.
  getOnBattery: () => ipcRenderer.invoke('vael:power-battery:get'),
  onBatteryChanged: callback => {
    const listener = (_event, onBattery) => callback(Boolean(onBattery))
    ipcRenderer.on('vael:power-battery', listener)

    return () => ipcRenderer.removeListener('vael:power-battery', listener)
  },
  onBootProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('vael:boot-progress', listener)

    return () => ipcRenderer.removeListener('vael:boot-progress', listener)
  },
  // First-launch bootstrap progress -- emitted by the install.ps1 stage
  // runner in main.ts (apps/desktop/electron/bootstrap-runner.ts).
  // Renderer's install overlay subscribes to live events and queries the
  // current snapshot via getBootstrapState() to recover after a devtools
  // reload mid-bootstrap.
  getBootstrapState: () => ipcRenderer.invoke('vael:bootstrap:get'),
  probeLocalBackend: () => ipcRenderer.invoke('vael:local-backend:probe'),
  continueBootstrapLocal: () => ipcRenderer.invoke('vael:bootstrap:continue-local'),
  recycleBackend: profile => ipcRenderer.invoke('vael:backend:recycle', profile),
  resetBootstrap: () => ipcRenderer.invoke('vael:bootstrap:reset'),
  repairBootstrap: () => ipcRenderer.invoke('vael:bootstrap:repair'),
  cancelBootstrap: () => ipcRenderer.invoke('vael:bootstrap:cancel'),
  onBootstrapEvent: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('vael:bootstrap:event', listener)

    return () => ipcRenderer.removeListener('vael:bootstrap:event', listener)
  },
  getVersion: () => ipcRenderer.invoke('vael:version'),
  relaunchApp: () => ipcRenderer.invoke('vael:app:relaunch'),
  getMachineProfile: () => ipcRenderer.invoke('vael:machine:profile'),
  getRemoteDisplayReason: () => ipcRenderer.invoke('vael:get-remote-display-reason'),
  uninstall: {
    summary: () => ipcRenderer.invoke('vael:uninstall:summary'),
    run: mode => ipcRenderer.invoke('vael:uninstall:run', { mode })
  },
  updates: {
    check: opts => ipcRenderer.invoke('vael:updates:check', opts),
    apply: opts => ipcRenderer.invoke('vael:updates:apply', opts),
    getBranch: () => ipcRenderer.invoke('vael:updates:branch:get'),
    setBranch: name => ipcRenderer.invoke('vael:updates:branch:set', name),
    onProgress: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('vael:updates:progress', listener)

      return () => ipcRenderer.removeListener('vael:updates:progress', listener)
    },
    takePendingRun: () => ipcRenderer.invoke('vael:updates:metric:take'),
    ackPendingRun: sent => ipcRenderer.invoke('vael:updates:metric:ack', sent),
    onPendingRun: callback => {
      const listener = () => callback()
      ipcRenderer.on('vael:updates:metric:pending', listener)

      return () => ipcRenderer.removeListener('vael:updates:metric:pending', listener)
    }
  },
  desktopMetrics: {
    setEnabled: (on, profile) => ipcRenderer.invoke('vael:desktop-metrics:set-enabled', on, profile),
    takeRendererCrashes: () => ipcRenderer.invoke('vael:desktop-metrics:crash:take'),
    ackRendererCrashes: sent => ipcRenderer.invoke('vael:desktop-metrics:crash:ack', sent)
  },
  themes: {
    fetchMarketplace: id => ipcRenderer.invoke('vael:vscode-theme:fetch', id),
    searchMarketplace: query => ipcRenderer.invoke('vael:vscode-theme:search', query)
  },
  // Find-in-page (Ctrl/Cmd+F): delegates to Electron's
  // webContents.findInPage on the IPC sender's window so a Cmd+F pressed
  // in a secondary session window searches THAT window, not the primary.
  // `onFoundInPage` returns the unsubscribe fn; the renderer wires it via
  // `initFindInPageListener` in store/find-in-page.ts and tears it down
  // when the FindBar unmounts.
  findInPage: (query, options) => ipcRenderer.invoke('vael:find-in-page', query, options),
  stopFindInPage: () => ipcRenderer.invoke('vael:stop-find-in-page'),
  onFoundInPage: callback => {
    const listener = (_event, result) => callback(result)
    ipcRenderer.on('vael:found-in-page', listener)

    return () => ipcRenderer.removeListener('vael:found-in-page', listener)
  },
  // Main-process `before-input-event` forwards Ctrl/Cmd+F here so renderer
  // can open the FindBar even when the GTK compositor has already grabbed
  // the chord at the windowing layer (#81727).
  onOpenFindBarRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('vael:open-find-bar', listener)

    return () => ipcRenderer.removeListener('vael:open-find-bar', listener)
  }
})
