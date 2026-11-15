<#
.SYNOPSIS
  Authenticode-sign files with Microsoft Artifact Signing (formerly Trusted Signing).

.DESCRIPTION
  Used three ways:
    * by build.ps1 for the bundled executables (HermiSim.exe, hermisim-cli.exe, tulpa.exe)
    * by Inno Setup as its SignTool, for the setup executable and its uninstaller
    * by hand:  powershell -File installer\windows\sign.ps1 dist\installer\HermiSim-Setup-2.1.0-x64.exe

  Configuration comes from the environment:
    ARTIFACT_SIGNING_ENDPOINT   e.g. https://eus.codesigning.azure.net   (region of your account)
    ARTIFACT_SIGNING_ACCOUNT    Artifact Signing account name
    ARTIFACT_SIGNING_PROFILE    certificate profile name
  Authentication uses DefaultAzureCredential: in GitHub Actions the azure/login step (OIDC) makes
  AzureCliCredential available; locally `az login` works, or AZURE_CLIENT_ID/AZURE_TENANT_ID/
  AZURE_CLIENT_SECRET for a service principal.

  SignTool and the Artifact Signing dlib are fetched from NuGet into build\signing on first use.
#>
param([Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)][string[]]$Files)
$ErrorActionPreference = "Stop"

foreach ($v in "ARTIFACT_SIGNING_ENDPOINT", "ARTIFACT_SIGNING_ACCOUNT", "ARTIFACT_SIGNING_PROFILE") {
  if (-not [Environment]::GetEnvironmentVariable($v)) { throw "sign.ps1: $v is not set" }
}

$Root = Resolve-Path "$PSScriptRoot\..\.."
$Tools = Join-Path $Root "build\signing"
New-Item -ItemType Directory -Force $Tools | Out-Null

function Get-NuGet {
  $n = Get-Command nuget.exe -ErrorAction SilentlyContinue
  if ($n) { return $n.Source }
  $local = Join-Path $Tools "nuget.exe"
  if (-not (Test-Path $local)) {
    Invoke-WebRequest "https://dist.nuget.org/win-x86-commandline/latest/nuget.exe" -OutFile $local
  }
  return $local
}

# SignTool (Windows SDK build tools) + Artifact Signing dlib, pinned to known-good versions.
$signtool = Get-ChildItem $Tools -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -match "\\x64\\" } | Select-Object -First 1
$dlib = Get-ChildItem $Tools -Recurse -Filter Azure.CodeSigning.Dlib.dll -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -match "\\x64\\" } | Select-Object -First 1
if (-not $signtool -or -not $dlib) {
  $nuget = Get-NuGet
  & $nuget install Microsoft.Windows.SDK.BuildTools -x -OutputDirectory $Tools -NonInteractive | Out-Null
  & $nuget install Microsoft.ArtifactSigning.Client -x -OutputDirectory $Tools -NonInteractive | Out-Null
  $signtool = Get-ChildItem $Tools -Recurse -Filter signtool.exe | Where-Object { $_.FullName -match "\\x64\\" } | Select-Object -First 1
  $dlib = Get-ChildItem $Tools -Recurse -Filter Azure.CodeSigning.Dlib.dll | Where-Object { $_.FullName -match "\\x64\\" } | Select-Object -First 1
  if (-not $signtool -or -not $dlib) { throw "sign.ps1: could not obtain signtool.exe / Azure.CodeSigning.Dlib.dll" }
}

$metadata = Join-Path $Tools "metadata.json"
@{
  Endpoint               = $env:ARTIFACT_SIGNING_ENDPOINT.TrimEnd("/")
  CodeSigningAccountName = $env:ARTIFACT_SIGNING_ACCOUNT
  CertificateProfileName = $env:ARTIFACT_SIGNING_PROFILE
  ExcludeCredentials     = @("ManagedIdentityCredential", "SharedTokenCacheCredential",
                             "VisualStudioCredential", "VisualStudioCodeCredential",
                             "InteractiveBrowserCredential")
} | ConvertTo-Json | Set-Content $metadata -Encoding utf8

foreach ($f in $Files) {
  $f = $f.Trim('"')
  if (-not (Test-Path $f)) { throw "sign.ps1: no such file: $f" }
  for ($attempt = 1; $attempt -le 3; $attempt++) {
    & $signtool.FullName sign /v /fd SHA256 /tr "http://timestamp.acs.microsoft.com" /td SHA256 `
      /d "HermiSim" /du "https://github.com/LoQiseaking69/HermiSim-DynamicsViewer" `
      /dlib $dlib.FullName /dmdf $metadata $f
    if ($LASTEXITCODE -eq 0) { break }
    if ($attempt -eq 3) { throw "sign.ps1: signing failed for $f" }
    Start-Sleep -Seconds (5 * $attempt)   # transient timestamp/service errors
  }
  & $signtool.FullName verify /pa /q $f
  if ($LASTEXITCODE) { throw "sign.ps1: signature on $f does not verify" }
  Write-Host "signed: $f"
}
exit 0
