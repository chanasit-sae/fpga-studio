; Inno Setup Script for FPGA Studio (Spotify Dark Edition)
; Generates a professional Windows Setup Installer: FPGA_Studio_Setup_v4.3.exe

#define MyAppName "FPGA Studio"
#define MyAppVersion "4.3"
#define MyAppPublisher "FPGA Studio"
#define MyAppExeName "FPGA Studio.exe"
; SourcePath is provided by ISPP = folder containing this script
#define SourceDir RemoveBackslashUnlessRoot(SourcePath)

[Setup]
AppId={{5F8D3491-912A-4C2E-8E28-76A6C7B2F6E1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/posweeza558/fpga-studio
AppSupportURL=https://github.com/posweeza558/fpga-studio/issues
AppUpdatesURL=https://github.com/posweeza558/fpga-studio/releases
VersionInfoVersion=4.3.0.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
DefaultGroupName={#MyAppName}
OutputDir={#SourceDir}\installer_output
OutputBaseFilename=FPGA_Studio_Setup_v4.3
SetupIconFile={#SourceDir}\app_icon.ico
UninstallDisplayIcon={app}\app_icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Main application binaries from dist\FPGA Studio
Source: "{#SourceDir}\dist\FPGA Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Built-in 32-bit FPGA CPUs (OpenMIPS & Synthesizable RISC-V RV32IM only — no user custom CPUs)
Source: "{#SourceDir}\custom_cpus\openmips\*"; DestDir: "{app}\custom_cpus\openmips"; Excludes: "cpu_manifest.json"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\custom_cpus\riscv\*"; DestDir: "{app}\custom_cpus\riscv"; Excludes: "cpu_manifest.json"; Flags: ignoreversion recursesubdirs createallsubdirs
; xPack GCC 15.2 toolchain & openFPGALoader (Direct JTAG In-App Flasher)
Source: "{#SourceDir}\toolchain\*"; DestDir: "{app}\toolchain"; Flags: ignoreversion recursesubdirs createallsubdirs
; Pre-bundled hardware CPU Bitstreams (OpenMIPS, RISC-V, Nexys A7 Demo - No Vivado needed!)
Source: "{#SourceDir}\bitstreams\*"; DestDir: "{app}\bitstreams"; Flags: ignoreversion recursesubdirs createallsubdirs
; Application icon
Source: "{#SourceDir}\app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\app_icon.png"; DestDir: "{app}"; Flags: ignoreversion
; Fonts (if any)
Source: "{#SourceDir}\fonts\*"; DestDir: "{app}\fonts"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: WORKSPACE IS EXCLUDED AS REQUESTED! The application creates a clean workspace upon first launch.

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// The bundled GCC toolchains reach 152 chars below {app}, e.g.
// toolchain\xpack-riscv-...\include\c++\15.2.0\ext\pb_ds\detail\...
// Windows MAX_PATH is 260, so a long install folder makes setup fail
// mid-way with "MoveFile failed; code 3". Reject it up front instead.
const
  MaxAppDirLen = 97;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    if Length(WizardDirValue) > MaxAppDirLen then
    begin
      MsgBox('The destination folder path is too long (' + IntToStr(Length(WizardDirValue)) + ' characters).'
        + #13#10#13#10 + 'FPGA Studio bundles GCC toolchains with deeply nested folders, so the'
        + ' install path must be at most ' + IntToStr(MaxAppDirLen) + ' characters.'
        + #13#10#13#10 + 'Please choose a shorter folder, for example:  C:\FPGA Studio',
        mbError, MB_OK);
      Result := False;
    end;
  end;
end;
