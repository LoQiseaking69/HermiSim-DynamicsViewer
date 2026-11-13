<#
.SYNOPSIS
  Builds the HermiSim Windows installer end to end.

.EXAMPLE
  # from the HermiSim repo root, with TulpaLang checked out next to it
  powershell -ExecutionPolicy Bypass -File installer\windows\build.ps1
  powershell -File installer\windows\build.ps1 -TulpaSrc C:\src\TulpaLang -Version 2.0.1 -Sign

.NOTES
  Needs: Rust (cargo), Python 3.10+, Inno Setup 6 (iscc on PATH or default install dir).
  Optional: Node + npx (to package the VS Code extension), signtool for -Sign.
#>
param(
  [string]$TulpaSrc = "..\TulpaLang",
  [string]$Version  = "2.0.0",
  [switch]$Sign,
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
  if (Get-Command npx -ErrorAction SilentlyContinue) {
    Push-Location editors\vscode
    npm ci --silent; npx --yes @vscode/vsce package -o ..\..\dist\tulpa-lang.vsix
    Pop-Location
  }
  Pop-Location
}

Step "Staging toolchain"
python installer\stage_toolchain.py $TulpaSrc

Step "Python dependencies"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller==6.*

Step "Regenerating brand assets"
python -m pip install cairosvg pillow
python tools\make_brand_assets.py

Step "PyInstaller bundle"
New-Item -ItemType Directory -Force build | Out-Null
(Get-Content installer\windows\version_info.txt) -replace "2, 0, 0, 0", (($Version.Split('.') + '0') -join ', ') -replace "'2.0.0'", "'$Version'" |
  Set-Content build\version_info.txt -Encoding utf8
pyinstaller installer\hermisim.spec --noconfirm --clean --distpath dist --workpath build\pyi
if ($LASTEXITCODE) { throw "pyinstaller failed" }

Step "Smoke test: bundled toolchain"
& dist\HermiSim\_internal\toolchain\bin\tulpa.exe -V
& dist\HermiSim\hermisim-cli.exe doctor
& dist\HermiSim\hermisim-cli.exe exec workspace\morty\board\motherboard.rav
if ($LASTEXITCODE) { throw "bundled smoke test failed" }

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
