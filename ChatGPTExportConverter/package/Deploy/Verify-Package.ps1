<#
.SYNOPSIS
  Checks every file in the package against Deploy\SHA256SUMS.txt.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\Deploy\Verify-Package.ps1
  Exit code 0 = all files match; 1 = a file is missing or changed.
#>
param([string]$PackageRoot = (Split-Path -Parent $PSScriptRoot))
$sums = Join-Path $PSScriptRoot 'SHA256SUMS.txt'
$bad = 0; $ok = 0
foreach ($line in Get-Content -LiteralPath $sums) {
    if ($line -match '^\s*#' -or $line -notmatch '^([0-9a-f]{64})\s+(.+)$') { continue }
    $expected = $Matches[1]; $rel = $Matches[2]
    $path = Join-Path $PackageRoot $rel
    if (-not (Test-Path -LiteralPath $path)) { Write-Warning "MISSING  $rel"; $bad++; continue }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { Write-Warning "CHANGED  $rel"; $bad++ } else { $ok++ }
}
if ($bad) { Write-Host "$bad problem(s), $ok file(s) OK." -ForegroundColor Red; exit 1 }
Write-Host "All $ok files match SHA256SUMS.txt." -ForegroundColor Green
exit 0
