; ──────────────────────────────────────────────────────────────────────────────
;  .RAV IDE (formerly HermiSim) — Windows installer (Inno Setup 6.2+)
;
;    iscc installer\windows\ravide.iss                         (after PyInstaller)
;    iscc /DAppVersion=2.4.0 /DSignTool=signtool installer\windows\ravide.iss
;
;  Input : dist\RAVIDE\  (PyInstaller one-folder bundle, see installer\ravide.spec)
;  Output: dist\installer\RAVIDE-Setup-<version>-x64.exe
;
;  AppId is unchanged from HermiSim, so this upgrades an existing HermiSim install in place.
; ──────────────────────────────────────────────────────────────────────────────

#ifndef AppVersion
  #define AppVersion "2.4.0"
#endif
#define AppName      ".RAV IDE"
#define AppDirName   "RAV IDE"
#define AppPublisher "HermiTech LLC"
#define AppURL       "https://github.com/LoQiseaking69/.RAV_IDE"
#define AppExe       "RAVIDE.exe"
#define Bundle       "..\..\dist\RAVIDE"
#define ToolBin      "{app}\_internal\toolchain\bin"

[Setup]
AppId={{6E3F0B7A-9C41-4D2E-A7B1-48D2C5E0F1A9}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
AppCopyright=Copyright (C) HermiTech LLC
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} Setup
DefaultDirName={autopf}\HermiTech\{#AppDirName}
DefaultGroupName=HermiTech\{#AppDirName}
DisableProgramGroupPage=yes
; Per-user install by default (no UAC prompt); the dialog lets admins install for everyone.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
ChangesEnvironment=yes
ChangesAssociations=yes
LicenseFile=..\..\LICENSE
InfoBeforeFile=welcome.rtf
OutputDir=..\..\dist\installer
OutputBaseFilename=RAVIDE-Setup-{#AppVersion}-x64
SetupIconFile=assets\ravide.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName} {#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4
; ── look & feel ──
WizardStyle=modern
WizardSizePercent=110,110
WizardImageFile=assets\wizard-large.bmp,assets\wizard-large@2x.bmp
WizardSmallImageFile=assets\wizard-small.bmp,assets\wizard-small@2x.bmp
WizardImageStretch=yes
WizardImageAlphaFormat=none
ShowLanguageDialog=no
SetupLogging=yes
CloseApplications=yes
RestartApplications=no
#ifdef SignTool
SignTool={#SignTool}
SignedUninstaller=yes
#endif

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Messages]
en.WelcomeLabel1=Welcome to [name]
en.WelcomeLabel2=This will install [name/ver] — the simulation suite and IDE for Tulpa.%n%nWrite robot software with physical units, contracts and state machines, then fly it against MuJoCo physics, cycle-accurate RTL models and real hardware.%n%nIncludes the Tulpa toolchain (compiler, VM, LSP, std/ libraries) and the Morty bipedal humanoid sample.
en.FinishedHeadingLabel=.RAV IDE is ready
en.FinishedLabel=[name] has been installed. Your editable projects live in Documents\RAV IDE (or your existing Documents\HermiSim folder).

[CustomMessages]
en.CompCore=.RAV IDE and MuJoCo simulator
en.CompTulpa=Tulpa toolchain (tulpa compiler, VM, language server, std/ libraries)
en.CompVSCode=Tulpa extension for Visual Studio Code (if VS Code is installed)
en.TaskDesktop=Create a &desktop shortcut
en.TaskPath=Add the &tulpa command to PATH
en.TaskAssoc=Open &.rav / .tlp Tulpa files with .RAV IDE
en.GroupIntegration=System integration:
en.LaunchMorty=Open the Morty sample project
en.Uninstalling=Removing tulpa from PATH...

[Types]
Name: "full";    Description: "Full installation"
Name: "compact"; Description: "IDE and toolchain only"
Name: "custom";  Description: "Custom"; Flags: iscustom

[Components]
Name: "core";   Description: "{cm:CompCore}";   Types: full compact custom; Flags: fixed
Name: "tulpa";  Description: "{cm:CompTulpa}";  Types: full compact custom; Flags: fixed

[Tasks]
Name: "desktopicon"; Description: "{cm:TaskDesktop}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "addtopath";   Description: "{cm:TaskPath}";    GroupDescription: "{cm:GroupIntegration}"
Name: "assoc";       Description: "{cm:TaskAssoc}";   GroupDescription: "{cm:GroupIntegration}"

[Files]
Source: "{#Bundle}\*"; DestDir: "{app}"; Components: core; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\ravide.ico"; DestDir: "{app}"; Components: core; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}";               Filename: "{app}\{#AppExe}"; IconFilename: "{app}\ravide.ico"; Comment: "Simulation suite & IDE for Tulpa"
Name: "{autoprograms}\{#AppName} (classic viewer)"; Filename: "{app}\{#AppExe}"; Parameters: "--classic"; IconFilename: "{app}\ravide.ico"
Name: "{autodesktop}\{#AppName}";                Filename: "{app}\{#AppExe}"; IconFilename: "{app}\ravide.ico"; Tasks: desktopicon

[Registry]
; .rav / .tlp → .RAV IDE (per-user or machine, following the install mode)
Root: HKA; Subkey: "Software\Classes\.rav";  ValueType: string; ValueName: ""; ValueData: "RAVIDE.TulpaSource"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.tlp";  ValueType: string; ValueName: ""; ValueData: "RAVIDE.TulpaSource"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\RAVIDE.TulpaSource"; ValueType: string; ValueName: ""; ValueData: "Tulpa source"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\RAVIDE.TulpaSource\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\ravide.ico,0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\RAVIDE.TulpaSource\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: assoc
; remove HermiSim-era registrations
Root: HKA; Subkey: "Software\Classes\HermiSim.TulpaSource"; Flags: deletekey dontcreatekey
Root: HKA; Subkey: "Software\Classes\Applications\HermiSim.exe"; Flags: deletekey dontcreatekey
Root: HKA; Subkey: "Software\HermiTech\HermiSim"; Flags: deletekey dontcreatekey
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".rav"; ValueData: ""; Flags: uninsdeletekey
; let the IDE find the bundled toolchain even when PATH wasn't touched
Root: HKA; Subkey: "Software\HermiTech\RAV IDE"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\HermiTech\RAV IDE"; ValueType: string; ValueName: "TulpaBin"; ValueData: "{#ToolBin}\tulpa.exe"

[Run]
Filename: "{cmd}"; Parameters: "/c code --install-extension ""{app}\_internal\toolchain\share\tulpa-lang.vsix"" --force"; Description: "{cm:CompVSCode}"; Flags: postinstall runhidden waituntilterminated skipifsilent; Check: HasVSCode and HasVsix
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#AppExe}"; Parameters: "morty"; Description: "{cm:LaunchMorty}"; Flags: nowait postinstall skipifsilent unchecked

[InstallDelete]
; upgrading a HermiSim install: drop the old executables, icon and shortcuts
Type: files; Name: "{app}\HermiSim.exe"
Type: files; Name: "{app}\hermisim-cli.exe"
Type: files; Name: "{app}\hermisim.ico"
Type: files; Name: "{autoprograms}\HermiSim.lnk"
Type: files; Name: "{autoprograms}\HermiSim (classic viewer).lnk"
Type: files; Name: "{autodesktop}\HermiSim.lnk"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal\__pycache__"
Type: filesandordirs; Name: "{localappdata}\RAV IDE\state"

[Code]
const
  EnvKeyUser = 'Environment';
  EnvKeyMachine = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';

function EnvRoot: Integer;
begin
  if IsAdminInstallMode then Result := HKEY_LOCAL_MACHINE else Result := HKEY_CURRENT_USER;
end;

function EnvKey: string;
begin
  if IsAdminInstallMode then Result := EnvKeyMachine else Result := EnvKeyUser;
end;

function HasVSCode: Boolean;
var
  Code: Integer;
begin
  Result := Exec(ExpandConstant('{cmd}'), '/c where code >nul 2>nul', '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
end;

function HasVsix: Boolean;
begin
  { decided at compile time: the vsix is only present if the toolchain was staged with one }
  Result := {#FileExists(AddBackslash(SourcePath) + Bundle + '\_internal\toolchain\share\tulpa-lang.vsix') ? 'True' : 'False'};
end;

{ ---- PATH editing that preserves REG_EXPAND_SZ and never duplicates entries ---- }
function PathContains(const Paths, Dir: string): Boolean;
begin
  Result := Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Paths) + ';') > 0;
end;

procedure AddToPath(const Dir: string);
var
  Paths: string;
begin
  if not RegQueryStringValue(EnvRoot, EnvKey, 'Path', Paths) then Paths := '';
  if PathContains(Paths, Dir) then Exit;
  if (Paths <> '') and (Copy(Paths, Length(Paths), 1) <> ';') then Paths := Paths + ';';
  Paths := Paths + Dir;
  if RegWriteExpandStringValue(EnvRoot, EnvKey, 'Path', Paths) then
    Log('Added to PATH: ' + Dir)
  else
    Log('Could not update PATH');
end;

procedure RemoveFromPath(const Dir: string);
var
  Paths: string;
  P: Integer;
begin
  if not RegQueryStringValue(EnvRoot, EnvKey, 'Path', Paths) then Exit;
  Paths := ';' + Paths + ';';
  P := Pos(';' + Uppercase(Dir) + ';', Uppercase(Paths));
  if P = 0 then Exit;
  Delete(Paths, P, Length(Dir) + 1);
  Paths := Copy(Paths, 2, Length(Paths) - 2);
  RegWriteExpandStringValue(EnvRoot, EnvKey, 'Path', Paths);
  Log('Removed from PATH: ' + Dir);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('addtopath') then
    AddToPath(ExpandConstant('{#ToolBin}'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    UninstallProgressForm.StatusLabel.Caption := CustomMessage('Uninstalling');
    RemoveFromPath(ExpandConstant('{#ToolBin}'));
  end;
end;

{ Upgrades: run the previous uninstaller silently so stale bundle files never linger. }
function PrevUninstaller: string;
var
  Key, S: string;
begin
  Result := '';
  Key := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6E3F0B7A-9C41-4D2E-A7B1-48D2C5E0F1A9}_is1';
  if RegQueryStringValue(HKLM, Key, 'UninstallString', S) or RegQueryStringValue(HKCU, Key, 'UninstallString', S) then
    Result := RemoveQuotes(S);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  U: string;
  Code: Integer;
begin
  Result := '';
  U := PrevUninstaller;
  if (U <> '') and FileExists(U) then
    Exec(U, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

procedure InitializeWizard;
begin
  { brand accent on the wizard chrome }
  WizardForm.WelcomeLabel1.Font.Color := $00FF6B5A;      { BGR: #5A6BFF brand indigo }
  WizardForm.FinishedHeadingLabel.Font.Color := $00FF6B5A;
  WizardForm.PageNameLabel.Font.Style := [fsBold];
end;
