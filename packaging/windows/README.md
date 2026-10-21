# Windows packaging and release checks

This guide covers FR-048 / AC-069 and the Windows host portion of FR-053 /
AC-076. It describes the local build and remaining release checks; it does not
mark either acceptance criterion as passed. Runtime recovery policy remains in
[OPERATIONS.md](../../docs/OPERATIONS.md) and the approved
[A11 backup boundary decision](../../legacy/docs/A11_BACKUP_BOUNDARY_DECISION_2026-10-03.md).

## Recorded status on 2026-10-03

| Check                                  | Recorded result and limit                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Latest PyInstaller and installer build | The [final candidate build log](../../release-evidence/a7/parallel-20261003/windows-build-repeat-focus.log) records successful complete `build_windows.ps1`, including the final A7 Web/API changes, root software LICENSE, notices, freeze, exact production Inno installer and checksums.                                                                                                                                                                                                                                                                               |
| Final installed launcher and A11       | The [installer receipt](../../release-evidence/a8/parallel-20261003/final-repeat-focus/installer-result.json) and [installed frozen API receipt](../../release-evidence/a8/parallel-20261003/final-repeat-focus-installed-maintenance/frozen-maintenance-result.json) record installed health/quit and encrypted backup/restore success against synthetic data, followed by a synthetic-version fixture upgrade and uninstall with all seven external files unchanged. This is a development-host/API fixture; its working directory is under the checkout evidence tree. |
| A11 browser download                   | The [native-download receipt](../../release-evidence/a11/browser-native-download-20261003.json) records completed zh-TW and English downloads of identical authenticated ciphertext. Downloaded-file upload/inspection/cancellation, fixture restore and eight bilingual responsive profiles have saved partial local evidence; final installed browser and full accessibility acceptance remain open.                                                                                                                                                                    |
| Current source checks                  | Full Web: 484 tests in 42 files; affected Python: 226 passed; Ruff: 258 files; mypy: 103 source files, all passed. Earlier full Python baseline: 2,497 passed with two existing Windows skips before the native GET addition. The affected subset overlaps that baseline and is not a new full total. Root verified 112 wheel files, 102 frozen modules plus six namespaces, eight resources, 15 compiled Web files and all 300 checksum entries against the final artifacts.                                                                                             |
| Inno Setup                             | Official pinned portable Inno Setup 6.7.3 was verified by release SHA-256 and valid Pyrsys B.V. signature. An exact production recompile reproduced Root's final installer bytes. The separate fixture install, installed A11, synthetic 0.1.0-to-0.1.1 registration transition and uninstall passed; clean-account and released-version upgrade acceptance remain open.                                                                                                                                                                                                  |
| License                                | Owner-approved MIT software text is present in root LICENSE and included in the final onedir. Dependency/native license and source-availability review remain open; software licensing does not establish artwork or model redistribution rights.                                                                                                                                                                                                                                                                                                                         |
| Release                                | `dist/windows/RELEASE-GATES.txt` records outstanding checks. No public release, clean-account acceptance, signing or SmartScreen walkthrough is claimed.                                                                                                                                                                                                                                                                                                                                                                                                                  |

The final executable SHA-256 is
`d0170458eeefde6723acd5eb888fc49d042ffb4201096f05532de9f527715283`.
The exact production installer SHA-256 is
`ff87ae23b55d3ada11ad96c2f230a987200d9a6822f7ac383412179b4e4e0b5f`;
recompiling the unchanged production recipe from the isolated snapshot produced
identical bytes. The earlier outside-checkout health smoke remains historical
([receipt](../../release-evidence/a6/windows-frozen-smoke-a11-native-final-20261003.json),
exit 0 in 2.3415 seconds, executable `12cb22f65be4a66fae8006f263452659be537a2a40e06c2c3f70407c29ced2ff`).
The installed API fixture adds final-binary evidence without replacing clean-host
or native browser acceptance. Future source or Web changes require another build
and artifact-bound verification. Keep inputs, arguments, exit codes, source
fingerprints, checksums and results together.

The repeat-focus rebuild includes Root's same-card re-selection fix after locale
changes. Its [native browser record](../../release-evidence/a7/parallel-20261003/browser-repeat-focus.json)
shows heading focus on first/repeated selection and after switching zh-TW to
English at 375 pixels, with no horizontal overflow, no automatic profile writes
and no recorded console errors. This remains synthetic catalog/UI evidence.
The previous `final-candidate` installer/maintenance receipts remain preserved
as their earlier valid binary snapshot.

The earlier source checks are saved in the
[Web log](../../release-evidence/a6/web-a11-native-download-final-20261003.log),
[Python baseline log](../../release-evidence/a6/python-a11-final-20261003.log),
[affected Python log](../../release-evidence/a6/python-a11-native-root-final-20261003.log),
[Ruff log](../../release-evidence/a6/ruff-a11-native-final-20261003.log),
[mypy log](../../release-evidence/a6/mypy-a11-native-final-20261003.log), and
[wheel log](../../release-evidence/a6/wheel-a11-native-final-20261003.log).
The baseline and affected subset overlap and must not be added as a new total.

## Build on Windows

Use a Windows x64 build host with the repository's uv and pnpm versions. The
build script installs locked dependencies, builds the production Web files,
generates notices, freezes the onedir application, and writes checksums and
release gates. The `windows-build` group pins PyInstaller and its hooks. It does
not enable the `indexer` extra or include model weights.

From the checkout root, an explicit executable-only build is:

```powershell
pwsh -NoProfile -File scripts/build_windows.ps1 -SkipInstaller
```

When an existing Inno Setup 6.3 or newer compiler is available, compile the
installer with:

```powershell
pwsh -NoProfile -File scripts/build_windows.ps1 -IsccPath 'C:\BuildTools\Inno Setup 6\ISCC.exe'
```

The example compiler path must be replaced with the installed compiler's actual
location. The script does not install Inno Setup. Without `-SkipInstaller`, an
absent or unsupported compiler fails before dependency installation or output
mutation. Do not use the installer command as evidence that installation ran.

The output is `dist/windows/RepoNPC/RepoNPC.exe` plus its required `_internal`
directory. Keep the entire onedir tree together. The installer, when compiled,
is `dist/windows/RepoNPC-Setup-<version>.exe`; version comes solely from
`pyproject.toml`. The recipe also accepts `/DAppVersion`, `/DBuildRoot` and
`/DOutputRoot` compiler parameters without a generated `.iss` file.

`THIRD_PARTY_NOTICES.txt` is generated from installed locked runtime dependencies,
active runtime extras, the Python runtime, PyInstaller's bootloader exceptions,
production Web dependencies and font OFL. Exact pinned license supplements are
recorded in `licenses/sources.json`. The helper fails closed on missing text;
generation does not replace the final license review, including native vendored
components and applicable source-availability obligations. Root project license
text is now present and must be included in the final artifact; artwork and model
rights remain separate release checks.

## Launch and disposable smoke

Normal launch selects an available loopback port, waits for `/healthz`, then opens
the admin page using a short-lived local-launch grant. The console accepts
`open` to reopen the page and `quit` to stop the owned server. It does not start a
public visitor gateway or automatically select, download or call a model.
`--no-browser` suppresses browser opening; `--smoke-check` checks health and stops
without entering the interactive console.

For a bounded smoke against fresh disposable data, use an explicit directory:

```powershell
$smokeData = Join-Path ([IO.Path]::GetTempPath()) ('reponpc-smoke-' + [guid]::NewGuid().ToString('N'))
& .\dist\windows\RepoNPC\RepoNPC.exe --no-browser --smoke-check --data-dir $smokeData
if ($LASTEXITCODE -ne 0) { throw 'Frozen launcher smoke failed.' }
```

Record the exit code even when the program emits no output. This smoke can create
fixture SQLite and host identity-key files in the specified directory. It does
not exercise a real owner database, model inference, installation, upgrade,
uninstall or the complete browser restore flow. Run it again against each final
artifact from a working directory outside the checkout.

## Installation and retained data

The per-user recipe requires Windows 11 x64, requests no administrator elevation,
and uses the stable AppId `{9B5F80E7-BE26-49B4-9939-9F85D69FF4EC}`. Program files
default to `%LOCALAPPDATA%\Programs\RepoNPC`. The launcher independently owns
`%LOCALAPPDATA%\RepoNPC\data`; model artifacts and secret stores remain there.
The start-menu shortcut launches `RepoNPC.exe`; the desktop shortcut and
post-install launch are optional and unchecked. Silent installation does not
launch the application.

The recipe replaces installation files during upgrade and removes installation
files and shortcuts during uninstall. It has no runtime-data deletion rule,
`UninstallDelete` wildcard or automatic model/secret cleanup. This is the recipe
contract; verify preservation with an actual upgrade and uninstall on a clean
Windows account before claiming AC-069.

The [portable compiler receipt](../../release-evidence/a8/parallel-20261003/compiler-acquisition.json)
records the pinned official 6.7.3 download, checksum, publisher verification and
portable extraction. Its [acquisition script](../../release-evidence/a8/parallel-20261003/acquire_compiler.ps1)
does not install a global compiler. The official [portable-mode source](https://raw.githubusercontent.com/jrsoftware/issrc/is-6_7_3/isportable.iss)
disables uninstall registration and shortcuts for the compiler itself.

The [historical installer receipt](../../release-evidence/a8/parallel-20261003/historical-preliminary-2/installer-result.json)
binds executable SHA-256 `12cb22f65be4a66fae8006f263452659be537a2a40e06c2c3f70407c29ced2ff`
to the production recipe compile. The production installer SHA-256 is
`7662dcd44b54946b16b6fe8eb4f0c7175d477b3419917376e35eac4feb9176da`.
Only a separate fixture derivative was installed: fresh AppId, fixture shortcut
names, program directory under the evidence tree and forced external fixture
`--data-dir` in every launcher entry. `/DIR` alone cannot isolate uninstall
registry keys or shortcuts. The unchanged production identity was never installed.
The fixture installed, replaced its overlay sentinel during a same-version
reinstall, ran a model-free installed smoke, and uninstalled with exit 0. Its
HKCU uninstall key and start-menu group were removed; SQLite, host key and external
sentinel hashes remained unchanged. This proves a local overlay and preservation
case, not a released-version upgrade, clean account or dependency-free host.

The [final candidate receipt](../../release-evidence/a8/parallel-20261003/final-repeat-focus/installer-result.json)
adds the installed A11 walkthrough before upgrade, then changes only the fixture
installer's registered version from 0.1.0 to the synthetic next patch 0.1.1.
Its program overlay sentinel changes and the fixture registration records the
new version. After uninstall, all seven external files remain byte-identical:
runtime SQLite, fixture host key, synthetic model/asset/sentinel resources and
two authenticated encrypted backups. Fixture registry/shortcuts are gone; the
production recipe remains byte-identical. Every actual install/smoke/maintenance/
upgrade/uninstall command exits 0. The original fixed production AppId was never
installed, and no owner runtime was read or changed.

## A11 maintenance and backup boundary

Option A is owner-approved under ADR-054 / OR-028 and Approved Technical
Specification 0.4.7. The maintenance page prepares a password-encrypted SQLite
backup, then a protected native GET delivers the attachment through the browser
download flow. Both locales completed the same ciphertext download in the
disposable in-app browser check. The owner-approved initial scope is restoring SQLite state into the **same data
directory on the same host**. The artifact contains the owner authentication hash
and encrypted historical connection revisions only inside authenticated
ciphertext. Keep the backup password separately; stored passwords, host keys and
private connection values are not returned by the management API.

The artifact does not include host identity or model-secret keys, retained
bundles, model weights, scene/background assets or local portfolio originals.
Preserve these files separately. Copying the SQLite artifact to a new machine or
an empty data directory is not a supported full-installation recovery procedure.
Missing or incompatible keys, retained bundles or referenced appearance files
cause the restore check to fail; restore does not replace missing keys, fetch
resources or call providers.

The owner uploads the encrypted artifact and enters its backup password. The
service validates the encryption metadata, schema, integrity, foreign keys and
retained resources before presenting a session-bound confirmation. Confirmation
starts maintenance only after unfinished work is rejected. The owned host drains
requests, stops the old application lifespan, saves an encrypted backup of the
current state, and replaces the database with rollback protection. Rebuilding or
starting the replacement unsuccessfully restores the prior database and bundle
pointer.

Successful restore revokes old sessions and local-launch grants and disables the
visitor gateway, clearing its prior verification. Reopen admin with the launcher
to obtain a fresh local-launch grant. Gateway exposure requires a new explicit
owner action. Keep the terminal recovery procedures in OPERATIONS available when
the management application cannot start.

The disposable browser fixture in
[`release-evidence/a11/browser_maintenance_fixture.py`](../../release-evidence/a11/browser_maintenance_fixture.py)
uses real Main preparation and MaintenanceHost with synthetic owner data. Its
production password-login wrapper is only for browser acceptance; the shipped
local launcher continues to use its local-launch boundary. Fixture success does
not establish real owner-runtime or final frozen-executable restore acceptance.

The [saved restore state](../../release-evidence/a11/browser-native-restore-state-20261003.json)
records real Main/MaintenanceHost restoration using keyboard Space, Tab and Enter:
the synthetic CURRENT sentinel changed to BASELINE, session count and preview
count became zero, the gateway remained off, SQLite integrity was valid, and all
three host ciphertext backups authenticated. Reload required production login;
relogin with the retained synthetic owner account succeeded. The
[interaction record](../../release-evidence/a11/browser-native-interactions-20261003.json)
includes downloaded-file upload/inspection/cancellation, wrong-password handling,
cleared password fields, disabled confirmation and empty recorded browser error
logs. The [responsive record](../../release-evidence/a11/browser-native-responsive-20261003.json)
covers 375/768/1024/1440 pixels in both zh-TW and English: correct main language
and no horizontal overflow in all eight profiles. Phone/final screenshots were
also saved. These are partial disposable local checks; actual 200% zoom,
assistive-technology/full browser matrix, installed retained-bundle/gateway
browser behavior and the complete frozen-host restore walkthrough remain unverified.

The [historical frozen API walkthrough](../../release-evidence/a8/parallel-20261003/historical-frozen-maintenance-4/frozen-maintenance-result.json)
now records an executable-bound, disposable evidence-directory run on port 18766.
It exercised the real local-launch grant boundary, encrypted backup and identical
native GET bytes, wrong-password rejection, inspection/cancellation, confirmation
and CURRENT-to-BASELINE restoration. Sessions and grants became zero, the gateway
remained off, integrity and foreign keys passed, two host backups authenticated,
synthetic external resources stayed unchanged, and console `quit` exited 0.
HTTPX explicitly replayed its synthetic localhost Secure cookie because its
cookie handling differs from the browser localhost exception. This is an API
fixture against the historical executable, without retained-bundle or browser
coverage. The final installed binary now has the separate receipt below. Failed harness
attempts are preserved beside the passing run, including missing origin and
HTTPX cookie replay adjustments.

The [final installed frozen API receipt](../../release-evidence/a8/parallel-20261003/final-repeat-focus-installed-maintenance/frozen-maintenance-result.json)
binds the current executable to the same real launcher and MaintenanceHost path.
It additionally rejects tampered ciphertext and false confirmation with 400 and
invalid CSRF with 403, preserves the owner credentials, restores BASELINE,
revokes old sessions/grants and keeps the gateway off. It authenticates both
host backups and exits through console `quit` with code 0. This working directory
and disposable data are within the evidence tree; Python/uv and the checkout
exist on this development machine. Referenced retained bundles, native browser
startup/restoration and actual clean-account acceptance remain open.

## Checks still required before release

1. Include the owner-approved root license text and finish dependency/native
   license and source-availability review; regenerate notices and rebuild the
   final artifact.
2. Complete A11 actual 200% zoom, assistive-technology/full browser matrix and
   installed retained-bundle/gateway acceptance; verify backup, invalid upload,
   confirmation, session revocation and rollback on the frozen host using
   disposable data. The installed API restore and eight responsive profiles have
   saved evidence; final native-browser, retained-bundle and fault/rollback
   walkthroughs remain open.
3. Test the compiled final candidate's install, console/admin launch, health and quit
   on a clean Windows 11 x64 account without Python, uv, pnpm or the checkout.
4. Test an actual upgrade and uninstall, confirming the independent data
   directory, keys, models, retained bundles and assets are preserved.
5. Publish the exact final artifact SHA-256 values and unsigned-build SmartScreen
   instructions after owner release approval. Never instruct users to disable
   platform protections globally.

Actual model quality, the reviewed model-guidance catalog, final A9 artwork and
redistribution rights, and external Funnel/Pages/GitHub checks remain open. The
historical acceptance ledger is unchanged; the
[new A11 candidate](../../release-evidence/a11/acceptance-ledger-candidate-20261003.json)
enumerates 79 rows with 76 `not-run` and three `blocked` (AC-020/037/069). Enumeration does not
close AC-069 or AC-076.

Existing CI verifies the source and Linux build; there is currently no Windows
installer release workflow. This guide adds no scheduled publication, hosted
service, signing setup or CI release authority.
