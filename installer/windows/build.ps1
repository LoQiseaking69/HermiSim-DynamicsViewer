<#
.SYNOPSIS
  Builds the HermiSim Windows installer end to end.

.EXAMPLE
  # from the HermiSim repo root, with TulpaLang checked out next to it
  powershell -ExecutionPolicy Bypass -File installer\windows\build.ps1
  powershell -File installer\windows\build.ps1 -TulpaSrc C:\src\TulpaLang -Version 2.0.3 -Sign

.NOTES
  Needs: Rust (cargo), Python 3.10+, Inno Setup 6 (iscc on PATH or default install dir).
  Optional: Node + npx (to package the VS Code extension), signtool for -Sign.
#>
param(
  [string]$TulpaSrc = "..\TulpaLang",
  [string]$Version  = "2.0.3",
  [switch]$Sign,
  [switch]$Brand,
  [switch]$SkipTulpa
)
$ErrorActionPreference = "Stop"
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
  # Rendered assets are committed; regenerate only on request (cairosvg needs the Cairo DLL).
  Step "Regenerating brand assets"
  python -m pip install cairosvg pillow
  python tools\make_brand_assets.py
  if ($LASTEXITCODE) { throw "brand asset rendering failed" }
}

Step "PyInstaller bundle"
New-Item -ItemType Directory -Force build | Out-Null
(Get-Content installer\windows\version_info.txt) -replace "2, 0, 0, 0", (($Version.Split('.') + '0') -join ', ') -replace "'2.0.0'", "'$Version'" |
  Set-Content build\version_info.txt -Encoding utf8
pyinstaller installer\hermisim.spec --noconfirm --clean --distpath dist --workpath build\pyi
if ($LASTEXITCODE) { throw "pyinstaller failed" }

Step "Smoke test: bundled toolchain"
& dist\HermiSim\_internal\toolchain\bin\tulpa.exe -V
$env:PYTHONIOENCODING = "utf-8"
& dist\HermiSim\hermisim-cli.exe doctor
if ($LASTEXITCODE) { throw "bundled doctor failed" }
& dist\HermiSim\hermisim-cli.exe exec workspace\morty\board\motherboard.rav
if ($LASTEXITCODE) { throw "bundled smoke test failed" }
# MuJoCo's Windows renderer is a hidden GLFW window: the DLL must ship inside the bundle.
if (-not (Get-ChildItem dist\HermiSim\_internal\glfw -Filter "glfw3*.dll" -Recurse -ErrorAction SilentlyContinue)) {
  throw "glfw3.dll missing from the bundle - the 3-D viewport would not render"
}
# Full co-simulation through the frozen app: Morty balancing for 2 s of sim time.
& dist\HermiSim\hermisim-cli.exe run workspace\morty\main.rav --model models\morty.xml --quiet -- 2
if ($LASTEXITCODE) { throw "bundled co-simulation failed" }

Step "Inno Setup"
$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) { $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
$isccArgs = @("/DAppVersion=$Version")
if ($Sign) { $isccArgs += '/DSignTool=signtool' ; $isccArgs += '/Ssigntool=signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /a $f' }
& $iscc @isccArgs installer\windows\hermisim.iss
if ($LASTEXITCODE) { throw "iscc failed" }

Get-ChildItem dist\installer\*.exe | ForEach-Object {
  $h = (Get-FileHash $_ -Algorithm SHA256).Hash
  "$h  $($_.Name)" | Tee-Object -FilePath "$($_.FullName).sha256"
}
Write-Host "`n✔ installer ready in dist\installer" -ForegroundColor Green
