[CmdletBinding()]
param(
  [string]$DbPath = (Join-Path $PSScriptRoot '..\backend\data\radar.db'),
  [string]$Destination = ''
)

$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath($DbPath)
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Database not found: $source" }
if ([string]::IsNullOrWhiteSpace($Destination)) {
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $Destination = Join-Path (Join-Path $PSScriptRoot '..\backups') "radar-$stamp.db"
}
$target = [IO.Path]::GetFullPath($Destination)
$parent = Split-Path -Parent $target
New-Item -ItemType Directory -Force -Path $parent | Out-Null
Copy-Item -LiteralPath $source -Destination $target -Force
if ((Get-Item -LiteralPath $target).Length -le 0) { throw "Backup is empty: $target" }
Write-Output "BACKUP_OK $target"
