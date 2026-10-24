[CmdletBinding(SupportsShouldProcess)]
param(
  [Parameter(Mandatory=$true)][string]$BackupPath,
  [string]$TargetPath = (Join-Path $PSScriptRoot '..\backend\data\radar.db')
)

$ErrorActionPreference = 'Stop'
$backup = [IO.Path]::GetFullPath($BackupPath)
$target = [IO.Path]::GetFullPath($TargetPath)
if (-not (Test-Path -LiteralPath $backup -PathType Leaf)) { throw "Backup not found: $backup" }
if ([IO.Path]::GetExtension($backup).ToLowerInvariant() -ne '.db') { throw 'Backup must be a .db file' }
if ($backup -eq $target) { throw 'Backup and target must be different paths' }
$parent = Split-Path -Parent $target
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$preserved = "$target.pre-restore-$(Get-Date -Format 'yyyyMMdd-HHmmss').db"
if ($PSCmdlet.ShouldProcess($target, "preserve original at $preserved and restore $backup")) {
  if (Test-Path -LiteralPath $target -PathType Leaf) { Copy-Item -LiteralPath $target -Destination $preserved -Force }
  Copy-Item -LiteralPath $backup -Destination $target -Force
  if ((Get-Item -LiteralPath $target).Length -le 0) { throw "Restored database is empty: $target" }
  Write-Output "RESTORE_OK $target PRESERVED_ORIGINAL $preserved"
}
