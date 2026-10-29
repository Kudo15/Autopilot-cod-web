#Requires -Version 5.1
<#
.SYNOPSIS
    Daily Radar: idempotent registration + status query of the per-user Task
    Scheduler job VuHocAIRadar-Daily (daily 07:00, local only).

.DESCRIPTION
    Che do:
      (mac dinh)     Dang ki task per-user 'VuHocAIRadar-Daily', chay daily 07:00
                     (gio dia phuong, host chay theo Asia/Ho_Chi_Minh), action:
                     <duong dan tuyet doi cua uv> run --no-sync python -m backend.app.radar.run_daily
                     trong <duong dan tuyet doi goc repo> (tinh tu $PSScriptRoot).
                     Idempotent: task da ton tai => in "already registered" va
                     exit 0, KHONG chinh sua, KHONG xoa gi ca.
      -Status        Tra cuu task: State, NextRunTime, LastRunTime,
                     LastTaskResult, Execute/Arguments/WorkingDirectory.
                     Task khong ton tai => loi ro + exit 1.

    Exit codes: 0 = OK (da dang ki, da ton tai nen bo qua, hoac tra cuu thanh cong);
                1 = task khong tim thay (che do -Status) hoac kiem tra sau dang ki that bai;
                2 = thieu dieu kien tien quyet (repo/uv/runner module).

    An toan:
      - Task per-user cho user dang nhap (LogonType Interactive, RunLevel
        Limited) — khong can mat khau, khong admin, chi chay tren may nay,
        khong co ket noi remote.
      - Script NAY khong bao gio Unregister/xoa task, khong dong database,
        khong bind cong.
      - Runner la one-shot: khong server, khong thread nen, khong goi mang,
        khong publish.

.EXAMPLE
    pwsh -File scripts/register_radar_task.ps1
    Dang ki idempotent task per-user chay daily 07:00.

.EXAMPLE
    pwsh -File scripts/register_radar_task.ps1 -Status
    Tra cuu trang thai task da dang ki.
#>
[CmdletBinding()]
param(
    [switch]$Status
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$TaskName = 'VuHocAIRadar-Daily'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Write-Ok { param([string]$Message) Write-Host "[ OK ] $Message" -ForegroundColor Green }
function Write-Bad { param([string]$Message) Write-Host "[FAIL] $Message" -ForegroundColor Red }

function Get-UvPath {
    <# Duong dan tuyet doi thuc cua lenh uv; $null neu thieu. #>
    $cmd = Get-Command 'uv' -ErrorAction SilentlyContinue
    if ($null -eq $cmd -or $null -eq $cmd.Source) { return $null }
    return [string]$cmd.Source
}

function Get-ExistingTask {
    try {
        return Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    } catch {
        return $null
    }
}

function Show-Status {
    $task = Get-ExistingTask
    if ($null -eq $task) {
        Write-Bad "Task '$TaskName' not found. Register first: pwsh -File scripts/register_radar_task.ps1"
        exit 1
    }
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    $action = @($task.Actions)[0]
    Write-Ok "Task '$TaskName' (per-user, daily 07:00):"
    Write-Host "       State          : $($task.State)"
    Write-Host "       NextRunTime    : $($info.NextRunTime)"
    Write-Host "       LastRunTime    : $($info.LastRunTime)"
    Write-Host "       LastTaskResult : $($info.LastTaskResult)"
    Write-Host "       Execute        : $($action.Execute)"
    Write-Host "       Arguments      : $($action.Arguments)"
    Write-Host "       WorkingDirectory: $($action.WorkingDirectory)"
    exit 0
}

if ($Status) { Show-Status }

# --- Idempotent: task da ton tai => khong thay doi gi ca ----------------------
$existing = Get-ExistingTask
if ($null -ne $existing) {
    Write-Ok "Task '$TaskName' already registered - no change (idempotent). Query with -Status."
    exit 0
}

# --- Dieu kien tien quyet: repo + uv + runner module --------------------------
$problems = New-Object System.Collections.Generic.List[string]
if (-not (Test-Path -LiteralPath (Join-Path $Root 'pyproject.toml'))) {
    $problems.Add("Repo root missing pyproject.toml: $Root")
}
$runnerModule = Join-Path $Root 'backend\app\radar\run_daily.py'
if (-not (Test-Path -LiteralPath $runnerModule)) {
    $problems.Add("Runner module missing: $runnerModule")
}
$uv = Get-UvPath
if ($null -eq $uv) {
    $problems.Add('uv not found in PATH - install uv (https://docs.astral.sh/uv/) then re-open the terminal')
}
if ($problems.Count -gt 0) {
    foreach ($problem in $problems) { Write-Bad $problem }
    exit 2
}

# --- Dang ki (duong dan tuyet doi: goc repo + uv) -----------------------------
$action = New-ScheduledTaskAction `
    -Execute $uv `
    -Argument 'run --no-sync python -m backend.app.radar.run_daily' `
    -WorkingDirectory $Root

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$trigger = New-ScheduledTaskTrigger -Daily -At (Get-Date '07:00:00')
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $TaskName -Action $action -Principal $principal -Trigger $trigger -Settings $settings -Description 'Vu Hoc AI Radar v1.0 - Daily Radar one-shot runner (local only, 07:00, no network, no publish)' | Out-Null

# Xac nhan bang tra cuu (khong tin loai tra ve cua lenh dang ki).
$check = Get-ExistingTask
if ($null -eq $check) {
    Write-Bad 'Register-ScheduledTask returned but the task is not queryable - check with -Status'
    exit 1
}
Write-Ok "Registered task '$TaskName' (per-user, daily 07:00, local only):"
Write-Host "       Execute        : $uv"
Write-Host "       WorkingDirectory: $Root"
Write-Host 'Next: pwsh -File scripts/register_radar_task.ps1 -Status'
exit 0
