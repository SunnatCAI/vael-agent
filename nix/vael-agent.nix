# nix/vael-agent.nix — Overridable VAEL Agent package
#
# callPackage auto-wires nixpkgs args; flake inputs are passed explicitly.
# Users override via:
#   pkgs.vael-agent.override { extraPythonPackages = [...]; }
#   pkgs.vael-agent.override { extraDependencyGroups = [ "honcho" ]; }
{
  lib,
  stdenv,
  makeWrapper,
  writeText,
  callPackage,
  electron,
  ripgrep,
  git,
  openssh,
  ffmpeg,
  tirith,

  # linux-only deps
  wl-clipboard,
  xclip,

  # linux-only dev deps
  cage,

  # Flake inputs — passed explicitly by packages.nix and overlays.nix
  uv2nix,
  pyproject-nix,
  pyproject-build-systems,
  npm-lockfile-fix,
  # Locked git revision of the flake source — embedded so banner.py can
  # check for updates without needing a local .git directory. Null for
  # impure / dirty builds where flakes can't determine a rev.
  rev ? null,
  branch ? null,
  dirty ? false,
  lastModified ? null,
  # Overridable parameters
  version ? "0.0.0",
  distance ? 0,
  extraPythonPackages ? [ ],
  extraDependencyGroups ? [ ],
}:
let
  # One owner (pythonLock.nix) reads pm/lock.json and selects the matching
  # nixpkgs interpreter. Everything Python-shaped below derives from it.
  pythonLock = callPackage ./pythonLock.nix { };
  python = pythonLock.interpreter;

  # Install stamp values — written to install-stamp.json so the Python
  # runtime (CLI, TUI) reads one file instead of env vars or .git probes.
  stampDistance =
    if builtins.isInt distance && distance >= 0 then distance else throw "distance must be a non-negative integer";
  stampDisplayVersion =
    if stampDistance > 0 && rev != null then
      "${version}+${toString stampDistance}.g${builtins.substring 0 7 rev}"
    else if stampDistance > 0 then
      throw "a non-zero distance requires an exact revision"
    else
      version;

  # CLI and Electron consume the same provenance and update owner.
  installStampFile = writeText "vael-install-stamp.json" (builtins.toJSON {
    schemaVersion = 2;
    commit = rev;
    commitDate = lastModified;
    inherit branch dirty;
    builtAt = null;
    baseVersion = version;
    displayVersion = stampDisplayVersion;
    distance = stampDistance;
    source = "nix";
    distribution = "nix";
    pmRuntime = toString pmRuntime;
    updateMechanism = "external";
    payload = "bootstrap";
    tag = null;
  });

  mkVaelVenv =
    extraDependencyGroups:
    callPackage ./python.nix {
      inherit uv2nix pyproject-nix pyproject-build-systems;
      pythonSrc = vaelNpmLib.pythonSrc;
      dependency-groups = [ "all" ] ++ extraDependencyGroups;
    };

  vaelVenv = (mkVaelVenv extraDependencyGroups).venv;

  pmRuntime = callPackage ./pm-runtime.nix {
    inherit uv2nix pyproject-nix pyproject-build-systems;
  };

  # Icons render on the runtime venv: Pillow and resvg-py are core dependencies.
  generatedIcons = callPackage ./icons.nix {
    inherit (mkVaelVenv [ ]) venv;
  };

  vaelNpmLib = callPackage ./lib.nix {
    inherit npm-lockfile-fix;
  };

  vaelTui = callPackage ./tui.nix {
    inherit vaelNpmLib;
  };

  vaelWeb = callPackage ./web.nix {
    inherit vaelNpmLib generatedIcons;
  };

  bundledSkills = lib.cleanSourceWith {
    src = ../skills;
    filter = path: _type: !(lib.hasInfix "/index-cache/" path) && !(lib.hasInfix "/__pycache__/" path);
  };

  # Optional skills are NOT in the wheel (pythonSrc excludes them, see
  # lib.nix) — the wrapper exposes them via VAEL_OPTIONAL_SKILLS, the
  # same mechanism Homebrew packaging uses.
  bundledOptionalSkills = lib.cleanSourceWith {
    src = ../optional-skills;
    filter = path: _type: !(lib.hasInfix "/index-cache/" path) && !(lib.hasInfix "/__pycache__/" path);
  };

  # Import bundled plugins (memory, context_engine, platforms/*).  Keeping
  # them out of the Python site-packages keeps import semantics identical
  # to a dev checkout — the loader reads them from VAEL_BUNDLED_PLUGINS.
  bundledPlugins = lib.cleanSourceWith {
    src = ../plugins;
    filter = path: _type: !(lib.hasInfix "/__pycache__/" path);
  };

  # i18n locale catalogs (locales/*.yaml). Shipped into the store and pointed
  # at by VAEL_BUNDLED_LOCALES so the wrapped binary always resolves human
  # strings instead of raw i18n keys (#23943 / #27632 / #35374).
  bundledLocales = lib.cleanSource ../locales;

  # Shipped MCP catalog (optional-mcps/<name>/manifest.yaml). Same bare-data-dir
  # case as locales: not a Python package, so it's symlinked into the store and
  # exposed via VAEL_OPTIONAL_MCPS.
  bundledOptionalMcps = lib.cleanSourceWith {
    src = ../optional-mcps;
    filter = path: _type: !(lib.hasInfix "/__pycache__/" path);
  };

  runtimeDeps = [
    vaelNpmLib.nodejs
    ripgrep
    git
    openssh
    ffmpeg
    tirith
  ]
  ++ lib.optionals stdenv.isLinux [
    wl-clipboard
    xclip
  ];

  runtimePath = lib.makeBinPath runtimeDeps;

  sitePackagesPath = python.sitePackages;

  # Only the offline assembler's import closure. A frontend or catalog edit
  # must not change this source, and no build output is read during evaluation.
  agentBuilderSrc = lib.fileset.toSource {
    root = ./..;
    fileset = lib.fileset.unions [
      ../scripts/build/agent.py
      ../scripts/build/inputs.py
      ../scripts/build/launchers.py
    ];
  };

  agentInputsFile = writeText "vael-agent-inputs.json" (builtins.toJSON {
    project = "${../pyproject.toml}";
    code = "${vaelVenv}/${sitePackagesPath}";
    repo = "share/vael-agent";
    placement = "references";
    target = "${if stdenv.hostPlatform.isDarwin then "darwin" else "linux"}-${
      if stdenv.hostPlatform.isAarch64 then "arm64" else "x64"
    }";
    python = "${vaelVenv}/bin/python3";
    site_packages = "${vaelVenv}/${sitePackagesPath}";
    environment = toString vaelVenv;
    pm_runtime = toString pmRuntime;
    command_dir = "${vaelVenv}/bin";
    resources = {
      skills = toString bundledSkills;
      optional-skills = toString bundledOptionalSkills;
      plugins = toString bundledPlugins;
      locales = toString bundledLocales;
      optional-mcps = toString bundledOptionalMcps;
    };
    frontends = {
      tui = "${vaelTui}/lib/vael-tui";
      web = toString vaelWeb;
    };
    ref = if dirty then null else rev;
    stamp = toString installStampFile;
    env = {
      VAEL_NODE = lib.getExe vaelNpmLib.nodejs;
    } // lib.optionalAttrs (rev != null && !dirty) {
      VAEL_REVISION = rev;
    };
  });

  # Walk propagatedBuildInputs to include transitive Python deps in PYTHONPATH.
  # Without this, a plugin listing e.g. requests as a dep would fail at runtime
  # if requests isn't already in the sealed uv2nix venv.
  allExtraPythonPackages = python.pkgs.requiredPythonModules extraPythonPackages;

  pythonPath = lib.makeSearchPath sitePackagesPath allExtraPythonPackages;

  checkPackageCollisions = ''
    import pathlib, sys, re

    def canonical(name):
        return re.sub(r'[-_.]+', '-', name).lower()

    # Collect core venv package names
    core = set()
    venv_sp = pathlib.Path('${vaelVenv}/${sitePackagesPath}')
    for di in venv_sp.glob('*.dist-info'):
        meta = di / 'METADATA'
        if meta.exists():
            for line in meta.read_text().splitlines():
                if line.startswith('Name:'):
                    core.add(canonical(line.split(':', 1)[1].strip()))
                    break

    # Check each extra package for collisions
    extras_dirs = [${lib.concatMapStringsSep ", " (p: "'${toString p}'") allExtraPythonPackages}]
    for edir in extras_dirs:
        sp = pathlib.Path(edir) / '${sitePackagesPath}'
        if not sp.exists():
            continue
        for di in sp.glob('*.dist-info'):
            meta = di / 'METADATA'
            if not meta.exists():
                continue
            for line in meta.read_text().splitlines():
                if line.startswith('Name:'):
                    pkg = canonical(line.split(':', 1)[1].strip())
                    if pkg in core:
                        print(f'ERROR: plugin package \"{pkg}\" collides with a package in vael sealed venv', file=sys.stderr)
                        print(f'  from: {di}', file=sys.stderr)
                        print(f'  Remove this dependency from extraPythonPackages.', file=sys.stderr)
                        sys.exit(1)
                    break

    print('No collisions found.')
  '';
in
stdenv.mkDerivation (finalAttrs: {
  pname = "vael-agent";
  inherit version;

  dontUnpack = true;
  dontBuild = true;
  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    runHook preInstall

    # uv2nix owns Python code and dependencies. The shared assembler only
    # links resources and emits the derived command/environment description.
    PYTHONPATH=${agentBuilderSrc} ${python}/bin/python3 -m scripts.build.agent \
      --inputs ${agentInputsFile} --out "$out"

    # Native wrappers retain Nix's PATH/PYTHONPATH policies. Names, executable
    # sources and resource bindings come from the builder, not another table.
    makeAgentWrapper() {
      local source="$1" destination="$2"
      shift 2
      makeWrapper "$source" "$out/$destination" "$@" \
        --suffix PATH : "${runtimePath}" \
        --set-default VAEL_BIN "$out/bin/vael"${
          lib.optionalString (extraPythonPackages != [ ])
            " \\\n        --suffix PYTHONPATH : \"${pythonPath}\""
        }
    }
    ${python}/bin/python3 - "$out/command-map.json" > "$TMPDIR/agent-wrappers.sh" <<'PY'
    import json, shlex, sys

    with open(sys.argv[1]) as handle:
        description = json.load(handle)
    env = [arg for key, value in sorted(description["env"].items())
           for arg in ("--set", key, value)]
    for command in description["commands"].values():
        print(shlex.join(["makeAgentWrapper", command["source"], command["destination"], *env]))
    PY
    source "$TMPDIR/agent-wrappers.sh"

    ${lib.optionalString (extraPythonPackages != [ ]) ''
      echo "=== Checking for plugin/core package collisions ==="
      ${vaelVenv}/bin/python3 -c "${checkPackageCollisions}"
      echo "=== No collisions ==="
    ''}

    runHook postInstall
  '';

  passthru =
    let
      devPython = (mkVaelVenv (extraDependencyGroups ++ [ "dev" ])).editableVenv;
    in
    {
      inherit
        vaelTui
        vaelWeb
        vaelNpmLib
        vaelVenv
        agentBuilderSrc
        agentInputsFile
        installStampFile
        pmRuntime
        python
        ;

      # `vaelDesktop` references `finalAttrs.finalPackage` (this whole
      # derivation, after all overrides are applied) so the desktop wrapper
      # can pin its `vael` command via VAEL_DESKTOP_VAEL. The
      # deployment override then picks up the fully wrapped
      # `vael` binary — venv with all deps, bundled skills/plugins,
      # runtime PATH (ripgrep/git/ffmpeg/etc).  No re-implementation
      # of the agent resolution in the desktop wrapper.
      vaelDesktop = callPackage ./desktop.nix {
        inherit vaelNpmLib electron installStampFile generatedIcons;
        python3 = python;
        vaelAgent = finalAttrs.finalPackage;
      };

      devShellHook = ''
        export VAEL_PYTHON=${devPython}/bin/python3
      '';

      devDeps =
        runtimeDeps
        ++ [
          devPython
        ]
        ++ lib.optionals stdenv.isLinux [
          cage # for running e2e tests without popping windows
        ];
    };

  meta = with lib; {
    description = "AI agent with advanced tool-calling capabilities";
    homepage = "https://github.com/NousResearch/hermes-agent";
    mainProgram = "vael";
    license = licenses.mit;
    platforms = platforms.unix;
  };
})
