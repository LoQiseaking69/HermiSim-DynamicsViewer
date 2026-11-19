<#
.SYNOPSIS
  Builds the .RAV IDE Windows installer end to end.

.EXAMPLE
  # from the repo root, with TulpaLang checked out next to it
  powershell -ExecutionPolicy Bypass -File installer\windows\build.ps1
  powershell -File installer\windows\build.ps1 -TulpaSrc C:\src\TulpaLang -Version 2.3.0 -Sign

.NOTES
  Needs: Rust (cargo), Python 3.10+, Inno Setup 6 (iscc on PATH or default install dir).
  Optional: Node + npx (to package the VS Code extension).

  -Sign signs RAVIDE.exe, ravide-cli.exe, tulpa.exe, the setup executable and its uninstaller
  with Microsoft Artifact Signing (see installer\windows\sign.ps1 for the required
  ARTIFACT_SIGNING_* variables and Azure login). -Sign is implied when RAVIDE_SIGN=1 (or the older HERMISIM_SIGN=1).
#>
param(
  [string]$TulpaSrc = "..\TulpaLang",
  [string]$Version  = "2.3.0",
  [switch]$Sign,
  [switch]$Brand,
  [switch]$SkipTulpa
)
$ErrorActionPreference = "Stop"
if ($env:RAVIDE_SIGN -eq "1" -or $env:HERMISIM_SIGN -eq "1") { $Sign = $true }
$Root = Resolve-Path "$PSScriptRoot\..\.."
Set-Location $Root

function Step($msg) { Write-Host "`n▸ $msg" -ForegroundColor Cyan }

if (-not $SkipTulpa) {
  Step "Building the Tulpa toolchain ($TulpaSrc)"
  Push-Location $TulpaSrc
  cargo build --release
  if ($LASTEXITCODE) { throw "cargo build failed" }
  if (Get-Command npm -ErrorAction SilentlyContinue) {
    Push-Location editors\vscode
    npm ci --no-audit --no-fund
    npm run package
    if ($LASTEXITCODE) { Write-Warning "VS Code extension packaging failed - continuing without it" }
    else {
      New-Item -ItemType Directory -Force ..\..\dist | Out-Null
      Get-ChildItem tulpa-lang-*.vsix | Sort-Object LastWriteTime | Select-Object -Last 1 |
        Copy-Item -Destination ..\..\dist\tulpa-lang.vsix -Force
    }
    Pop-Location
  }
  Pop-Location
}

Step "Staging toolchain"
python installer\stage_toolchain.py $TulpaSrc
if ($LASTEXITCODE) { throw "staging failed" }

Step "Python dependencies"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller==6.*
if ($LASTEXITCODE) { throw "pip install failed" }

if ($Brand) {
  # Rendered assets are committed; regenerate only on request.
  Step "Regenerating brand assets"
  python -m pip install pillow
  python tools\make_brand_assets.py
  if ($LASTEXITCODE) { throw "brand asset rendering failed" }
}

Step "PyInstaller bundle"
New-Item -ItemType Directory -Force build | Out-Null
(Get-Content installer\windows\version_info.txt) -replace "2, 0, 0, 0", (($Version.Split('.') + '0') -join ', ') -replace "'2.0.0'", "'$Version'" |
  Set-Content build\version_info.txt -Encoding utf8
pyinstaller installer\ravide.spec --noconfirm --clean --distpath dist --workpath build\pyi
if ($LASTEXITCODE) { throw "pyinstaller failed" }

Step "Smoke test: bundled toolchain"
& dist\RAVIDE\_internal\toolchain\bin\tulpa.exe -V
$env:PYTHONIOENCODING = "utf-8"
& dist\RAVIDE\ravide-cli.exe doctor
if ($LASTEXITCODE) { throw "bundled doctor failed" }
& dist\RAVIDE\ravide-cli.exe exec workspace\morty\board\motherboard.rav
if ($LASTEXITCODE) { throw "bundled smoke test failed" }
# MuJoCo's Windows renderer is a hidden GLFW window: the DLL must ship inside the bundle.
if (-not (Get-ChildItem dist\RAVIDE\_internal\glfw -Filter "glfw3*.dll" -Recurse -ErrorAction SilentlyContinue)) {
  throw "glfw3.dll missing from the bundle - the 3-D viewport would not render"
}
# Full co-simulation through the frozen app: Morty balancing for 2 s of sim time.
& dist\RAVIDE\ravide-cli.exe run workspace\morty\main.rav --model models\morty.xml --quiet -- 2
if ($LASTEXITCODE) { throw "bundled co-simulation failed" }

$SignScript = Join-Path $PSScriptRoot "sign.ps1"
if ($Sign) {
  Step "Signing bundled executables (Artifact Signing)"
  & $SignScript dist\RAVIDE\RAVIDE.exe dist\RAVIDE\ravide-cli.exe dist\RAVIDE\_internal\toolchain\bin\tulpa.exe
  if ($LASTEXITCODE) { throw "signing the bundle failed" }
}

Step "Inno Setup"
$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) { $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
$isccArgs = @("/DAppVersion=$Version")
if ($Sign) {
  # Inno calls this for the setup executable and the embedded uninstaller ($f = file to sign).
  $isccArgs += "/DSignTool=artifactsign"
  $isccArgs += "/Sartifactsign=powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$SignScript`" `$f"
}
& $iscc @isccArgs installer\windows\ravide.iss
if ($LASTEXITCODE) { throw "iscc failed" }

if ($Sign) {
  Step "Verifying signatures"
  $st = Get-ChildItem build\signing -Recurse -Filter signtool.exe | Where-Object { $_.FullName -match "\\x64\\" } | Select-Object -First 1
  Get-ChildItem dist\installer\*.exe | ForEach-Object {
    & $st.FullName verify /pa /v $_.FullName | Select-String "Issued to|Signing Certificate Chain|Successfully verified"
    if ($LASTEXITCODE) { throw "installer signature does not verify: $($_.Name)" }
  }
}

Get-ChildItem dist\installer\*.exe | ForEach-Object {
  $h = (Get-FileHash $_ -Algorithm SHA256).Hash
  "$h  $($_.Name)" | Tee-Object -FilePath "$($_.FullName).sha256"
}
Write-Host "`n✔ installer ready in dist\installer" -ForegroundColor Green
