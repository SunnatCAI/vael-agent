# VAEL CLI Reference

Live sources when anything looks stale: `vael --help`, `vael <command> --help`,
https://hermes-agent.nousresearch.com/docs/reference/cli-commands

### Global Flags

```
vael [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
vael chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
vael setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
vael model                Interactive model/provider picker
vael fallback [add|remove|list]  Fallback provider chain
vael config [show|edit|get|set|unset|path|env-path|check|migrate]
vael login / logout       OAuth sign-in / clear stored auth
vael doctor [--fix]       Check dependencies and config
vael status [--full]      Component summary (--full: every section)
```

### Tools & Skills

```
vael tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

vael skills list|browse|search QUERY|inspect ID
vael skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
vael skills config        Enable/disable skills per platform
vael skills check|update|uninstall|publish PATH
vael skills tap add REPO  Add a GitHub repo as a skill source
vael bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
vael mcp add NAME (--url or --command) | remove | list | test NAME
vael mcp catalog | install NAME     Curated catalog install
vael mcp configure NAME             Toggle tool selection
vael mcp serve                      Run VAEL as an MCP server
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
vael gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `vael photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/

### Sessions

```
vael sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

### Cron / Webhooks

```
vael cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
vael webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
vael profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
vael profile rename A B | alias NAME | export NAME | import FILE
vael profile migrate-identity A B   Retry a completed rename's session/routing identity migration
```

### Credentials & Pools

```
vael auth                 Interactive credential manager
vael auth add [PROVIDER]  Add OAuth or API-key credential (nous, openai-codex, qwen-oauth, …)
vael auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
vael desktop / gui        Native desktop app
vael dashboard            Web admin panel + embedded chat (--stop / --status)
vael proxy                OpenAI-compatible local proxy backed by an OAuth provider
vael portal               Quick setup / sign in via Nous Portal
vael kanban <verb>        Multi-agent work-queue board
vael project              Named multi-folder workspaces
vael skin list|use|set    Switch/tweak skins (see references/themes.md)
vael pets <verb>          Pet mascots (see references/petdex.md)
vael memory setup|status|off|reset   Memory provider
vael secrets bitwarden|onepassword   External secret stores
vael moa                  Mixture-of-Agents slots
vael hooks / security / backup / import / checkpoints / console
vael logs [-f] [errors]   View agent/error logs
vael send                 One-off message through a gateway platform
vael pairing / plugins / insights / journey / computer-use
vael acp                  ACP server (IDE integration)
vael completion bash|zsh|fish
vael update / uninstall / claw migrate
```

Plugin- and provider-supplied subcommands (e.g. `vael photon setup`) only appear once their plugin is installed/active.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `vael config edit` · [Configuration docs](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) |
| Tools / toolsets | `vael tools list` · [Tools reference](https://hermes-agent.nousresearch.com/docs/reference/tools-reference) |
| Skills catalog | `vael skills browse` · [Skills catalog](https://hermes-agent.nousresearch.com/docs/reference/skills-catalog) |
| Provider setup | `vael model` · [Providers guide](https://hermes-agent.nousresearch.com/docs/integrations/providers) |
| Env variables | `vael config env-path` · [Env vars reference](https://hermes-agent.nousresearch.com/docs/reference/environment-variables) |
| Gateway logs | `~/.vael/logs/gateway.log` (or `vael logs`) |
| Sessions | `vael sessions browse` (reads state.db) |
