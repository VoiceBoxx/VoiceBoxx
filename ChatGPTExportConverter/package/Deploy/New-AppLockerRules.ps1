<#
.SYNOPSIS
  Creates AppLocker rules that allow ChatGPT Export Converter (the .exe is not code-signed, so
  publisher rules are not possible yet).

.DESCRIPTION
  -RuleType Hash (default): one hash rule per .exe and .dll. Survives moving the folder, but must
  be regenerated for every new version.
  -RuleType Path: one path rule for the install folder. Only safe when standard users cannot write
  to that folder (true for %ProgramFiles%, NOT for %LOCALAPPDATA% per-user installs).

  Run on a reference computer where the program is installed (or point -Path at the package's App
  folder), then import the XML into your GPO / Intune policy, or merge with:
    Set-AppLockerPolicy -XmlPolicy .\ChatGPTExportConverter-AppLocker.xml -Merge

.EXAMPLE
  .\New-AppLockerRules.ps1 -Path 'C:\Program Files\ChatGPT Export Converter'
#>
param(
    [string]$Path = (Join-Path $env:ProgramFiles 'ChatGPT Export Converter'),
    [ValidateSet('Hash', 'Path')][string]$RuleType = 'Hash',
    [string]$User = 'Everyone',
    [string]$OutFile = '.\ChatGPTExportConverter-AppLocker.xml'
)
$ErrorActionPreference = 'Stop'
Import-Module AppLocker
if (-not (Test-Path -LiteralPath (Join-Path $Path 'ChatGPTExportConverter.exe'))) {
    throw "ChatGPTExportConverter.exe not found in $Path"
}
# .pyd files are Python extension DLLs; list them explicitly so DLL rules cover them too.
$files = Get-ChildItem -LiteralPath $Path -Recurse -File -Include *.exe, *.dll, *.pyd
$info = $files | ForEach-Object { Get-AppLockerFileInformation -Path $_.FullName }
$xml = $info | New-AppLockerPolicy -RuleType $RuleType -User $User -RuleNamePrefix 'ChatGPT Export Converter' -Optimize -Xml
Set-Content -LiteralPath $OutFile -Value $xml -Encoding UTF8
Write-Host "Wrote $OutFile ($(@($info).Count) files, $RuleType rules)."
Write-Host 'DLL rules (.dll/.pyd) only matter if AppLocker DLL rule enforcement is on. Check that the XML lists the .pyd files.'
