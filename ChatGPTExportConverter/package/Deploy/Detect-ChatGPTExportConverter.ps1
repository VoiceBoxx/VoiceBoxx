<#
.SYNOPSIS
  Detection script for Intune (Win32 app) and Configuration Manager (script detection method).

.DESCRIPTION
  Reports "installed" when ChatGPT Export Converter @VERSION@ or newer is installed by the MSI or by
  Install.cmd, and the program file is present. Both tools treat "text on STDOUT + exit code 0" as
  installed and "no output + exit code 0" as not installed.

  Intune: upload as the detection script; "Run script as 32-bit process on 64-bit clients" = No.
  Per-user installs (Install.cmd /CURRENTUSER) are found when the script runs in the user context.

.NOTES
  Works on Windows PowerShell 5.1 and PowerShell 7. Reads the registry only; changes nothing.
#>
$ErrorActionPreference = 'SilentlyContinue'
$MinimumVersion = [version]'@VERSION@'
$UninstallPath  = 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'

function Get-Entries([Microsoft.Win32.RegistryHive]$Hive) {
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey($Hive, [Microsoft.Win32.RegistryView]::Registry64)
    $root = $base.OpenSubKey($UninstallPath)
    if (-not $root) { return }
    foreach ($name in $root.GetSubKeyNames()) {
        $k = $root.OpenSubKey($name)
        if ($k -and $k.GetValue('DisplayName') -eq 'ChatGPT Export Converter') {
            [pscustomobject]@{
                Version  = $k.GetValue('DisplayVersion')
                Location = $k.GetValue('InstallLocation')
                Key      = "$Hive\$UninstallPath\$name"
            }
        }
    }
}

$found = @(Get-Entries LocalMachine) + @(Get-Entries CurrentUser)
foreach ($e in $found) {
    $v = $null
    if (-not [version]::TryParse([string]$e.Version, [ref]$v) -or $v -lt $MinimumVersion) { continue }
    $dir = $e.Location
    if (-not $dir) {
        # MSI entries don't always carry InstallLocation; fall back to the product's own key.
        $dir = (Get-ItemProperty 'HKLM:\SOFTWARE\ChatGPTExportConverter').InstallDir
    }
    if ($dir -and (Test-Path -LiteralPath (Join-Path $dir 'ChatGPTExportConverter.exe'))) {
        Write-Output "ChatGPT Export Converter $v installed in $dir"
        exit 0
    }
}
exit 0
