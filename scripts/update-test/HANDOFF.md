# testing the bundles branch against your normal vael install

instructions:

1. close vael, the gateway, etc. make sure you have no running vael processes.

2. apply my updater override:
   macos/linux:
   ```bash
   REPO_ID="sunnatilla0717/vael-agent"
   SHA=$(curl -fsSL -H "User-Agent: vael-installer" "https://api.github.com/repos/$REPO_ID/commits/main" | grep -m1 '"sha"' | cut -d'"' -f4)
   if [[ ! "$SHA" =~ ^[0-9a-f]{40}$ ]]; then echo "Failed to resolve commit SHA" >&2; exit 1; fi
   curl -fsSL "https://raw.githubusercontent.com/$REPO_ID/$SHA/scripts/update-test/vael-update-rehearsal.sh" | bash -s -- pre
   ```

   windows (open PowerShell with **Run as Administrator** — the backup takes a disk snapshot, which needs admin):
   ```powershell
   $repo_id = "sunnatilla0717/vael-agent"
   $sha = (irm "https://api.github.com/repos/$repo_id/commits/main" -Headers @{ "User-Agent" = "ps-installer" }).sha
   $scriptUrl = "https://raw.githubusercontent.com/$repo_id/$sha/scripts/update-test/vael-update-rehearsal.ps1"
   & ([scriptblock]::Create((irm $scriptUrl))) pre
   ```

   this backs up your entire vael home and any desktop app settings, then points your install's updates at the test fork's `main` (no local mirror: `vael update` fetches straight from the fork, so it needs network). _from this point on, nothing you do in vael will be preserved, until you restore your backup at the end._

3. boot vael up to ensure everything is working, still. if you normally have a background service, gateway, etc, make sure it's running.

4. update vael like you normally do.

5. test vael. make sure nothing breaks, everything you use still works, etc.

6. close vael, the gateway, etc. make sure you have no running vael processes.

7. restore your backup:

   macos/linux:
   ```bash
   REPO_ID="sunnatilla0717/vael-agent"
   SHA=$(curl -fsSL -H "User-Agent: vael-installer" "https://api.github.com/repos/$REPO_ID/commits/main" | grep -m1 '"sha"' | cut -d'"' -f4)
   if [[ ! "$SHA" =~ ^[0-9a-f]{40}$ ]]; then echo "Failed to resolve commit SHA" >&2; exit 1; fi
   curl -fsSL "https://raw.githubusercontent.com/$REPO_ID/$SHA/scripts/update-test/vael-update-rehearsal.sh" | bash -s -- post --yes
   ```

   windows (again as **Administrator**):
   ```powershell
   $repo_id = "sunnatilla0717/vael-agent"
   $sha = (irm "https://api.github.com/repos/$repo_id/commits/main" -Headers @{ "User-Agent" = "ps-installer" }).sha
   $scriptUrl = "https://raw.githubusercontent.com/$repo_id/$sha/scripts/update-test/vael-update-rehearsal.ps1"
   & ([scriptblock]::Create((irm $scriptUrl))) post -Yes
   ```

   this puts vael back to exactly how it was beforehand.

# testing the bundles branch from a fresh install

macos/linux, in a terminal

```bash
REPO_ID="sunnatilla0717/vael-agent"

SHA=$(curl -fsSL -H "User-Agent: vael-installer" "https://api.github.com/repos/$REPO_ID/commits/main" | grep -m1 '"sha"' | cut -d'"' -f4)

if [[ ! "$SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Failed to resolve commit SHA for $REPO_ID" >&2
  exit 1
fi

curl -fsSL "https://raw.githubusercontent.com/$REPO_ID/$SHA/scripts/install.sh" | VAEL_REPO_URL="https://github.com/$REPO_ID.git" bash
```

windows, in powershell

```powershell
$repo_id = "sunnatilla0717/vael-agent"
$sha = (irm "https://api.github.com/repos/$repo_id/commits/main" -Headers @{ "User-Agent" = "ps-installer" }).sha
$scriptUrl = "https://raw.githubusercontent.com/$repo_id/$sha/scripts/install.ps1"
$env:VAEL_REPO_URL = "https://github.com/$repo_id.git"
& ([scriptblock]::Create((irm $scriptUrl)))
```
