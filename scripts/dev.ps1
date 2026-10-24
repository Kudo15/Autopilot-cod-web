#Requires -Version 5.1
<#
.SYNOPSIS
    Khoi dong localhost mot lenh cho Vu Hoc AI Radar v1.0.

.DESCRIPTION
    Che do:
      -Check             Kiem tra dieu kien tien quyet (Node/npm/uv/Python, file bat buoc,
                         dependency, cong 8000/5173) roi thoat. Thieu dieu kien => exit code
                         khac 0 kem viec can lam cu the. Khong cai gi, khong mo server.
      (mac dinh)         Chay migration idempotent, mo backend 127.0.0.1:8000 va Vite
                         127.0.0.1:5173, cho toi khi ca hai tra HTTP, giu PID hien thi.
                         Ctrl+C dung dung hai tien trinh do script nay mo.

    An toan:
      - Chi bind 127.0.0.1 (khong bao gio 0.0.0.0). Khong deploy, khong push.
      - .env.example chi duoc doc de lay TEN bien; gia tri secret khong bao gio bi in,
        khong bao gio duoc tao/suy dien. Secret that phai nam trong environment.
      - -NoInstall: thieu dependency thi bao lenh can chay, khong tu cai qua mang.
      - Khong xoa du lieu, khong kill tien trinh la; chi dung cay tien trinh minh mo.

.PARAMETER Check
    Chi kiem tra roi thoat (exit 0 = san sang, khac 0 = thieu dieu kien tien quyet).

.PARAMETER NoInstall
    Khong chay uv sync / npm install ngam (chan cai qua mang ngoai y muon).

.PARAMETER BackendPort
    Cong backend (mac dinh 8000), chi bind 127.0.0.1.

.PARAMETER FrontendPort
    Cong Vite (mac dinh 5173), chi bind 127.0.0.1.

.PARAMETER AutoStopSeconds
    Chi dung cho kiem thu tu dong: tu dung sau N giay roi exit 0 (0 = chay toi khi Ctrl+C).

.EXAMPLE
    pwsh -File scripts/dev.ps1 -Check

.EXAMPLE
    pwsh -File scripts/dev.ps1
#>
[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$NoInstall,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [int]$AutoStopSeconds = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$LogsDir = Join-Path $Root '.dev-logs'

# Log uvicorn/Vite bang UTF-8 (tieng Viet) tren Windows console.
$env:PYTHONUTF8 = '1'

#: File bat buoc phai co truoc khi chay.
$RequiredFiles = @(
    'pyproject.toml',
    'package.json',
    'vite.config.js',
    'index.html',
    'backend/app/main.py',
    'backend/app/migrate.py',
    '.env.example'
)

function Write-Step { param([string]$Message) Write-Host "[dev]  $Message" }
function Write-Ok { param([string]$Message) Write-Host "[ OK ] $Message" -ForegroundColor Green }
function Write-Warn { param([string]$Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Bad { param([string]$Message) Write-Host "[FAIL] $Message" -ForegroundColor Red }

function Get-CommandPath {
    <# Duong dan thuc cua mot lenh (npm -> npm.cmd). $null neu khong co. #>
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $cmd -or $null -eq $cmd.Source) { return $null }
    return [string]$cmd.Source
}

function Invoke-Native {
    <#
        Chay mot lenh ben ngoai va tra ve @{ Code; Output }.
        $ErrorActionPreference duoc ha xuong Continue trong luc chay de exit code khac 0
        cua tien trinh ngoai khong bi doi thanh loi terminating (PowerShell 5.1 va 7.x),
        va de stderr cua tool khong lam gay script.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [switch]$Quiet
    )
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $output = @()
    $code = 0
    try {
        $output = @(& $FilePath @Arguments 2>&1 | ForEach-Object { "$_" })
        if ($null -ne $LASTEXITCODE) { $code = [int]$LASTEXITCODE }
    } catch {
        $output = @("$($_.Exception.Message)")
        if ($null -ne $LASTEXITCODE) { $code = [int]$LASTEXITCODE }
    } finally {
        $ErrorActionPreference = $previous
    }
    if (-not $Quiet) {
        foreach ($line in $output) { Write-Host "       $line" }
    }
    return @{ Code = $code; Output = @($output) }
}

function Test-PortFree {
    <# Cong 127.0.0.1:$Port chua co gi lang nghe => true. #>
    param([int]$Port)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(500)) { return $true }
        try {
            $client.EndConnect($async)
            return $false
        } catch {
            return $true
        }
    } catch {
        return $true
    } finally {
        $client.Close()
    }
}

function Get-EnvTemplateNames {
    <#
        Doc .env.example va CHI tra ve ten bien (KEY). Khong bao gio doc/in gia tri,
        nen khong the lo secret va cung khong the vo tinh tao secret gia.
    #>
    param([string]$Path)
    $names = New-Object System.Collections.Generic.List[string]
    if (-not (Test-Path -LiteralPath $Path)) { return @() }
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith('#')) { continue }
        $match = [regex]::Match($trimmed, '^([A-Za-z_][A-Za-z0-9_]*)=')
        if ($match.Success) {
            $name = $match.Groups[1].Value
            if (-not $names.Contains($name)) { $names.Add($name) }
        }
    }
    return @($names)
}

function Show-EnvTemplateStatus {
    param([string]$TemplatePath)
    $names = @(Get-EnvTemplateNames -Path $TemplatePath)
    if ($names.Count -eq 0) {
        Write-Warn "Khong doc duoc ten bien nao tu $TemplatePath"
        return
    }
    Write-Step ("Bien moi truong app can (theo template .env.example): " + ($names -join ', '))
    foreach ($name in $names) {
        $value = [Environment]::GetEnvironmentVariable($name, 'Process')
        if ([string]::IsNullOrWhiteSpace($value)) {
            Write-Warn "$name chua set trong environment. Gia tri that do BAN cung cap (vd: `$env:$name = '...'); khong dien vao .env.example."
        } else {
            Write-Ok "$name da set trong environment (gia tri khong hien thi)."
        }
    }
}

function Invoke-Preflight {
    <#
        Kiem tra tien quyet. Tra ve @{ Problems; Node; Npm; Uv; VenvPython }.
        Neu -AllowInstall thi cai dependency con thieu (uv sync + npm install);
        neu khong thi chi bao lenh can chay.
    #>
    param([switch]$AllowInstall)

    $problems = New-Object System.Collections.Generic.List[string]
    $node = Get-CommandPath 'node'
    $npm = Get-CommandPath 'npm.cmd'
    if ($null -eq $npm) { $npm = Get-CommandPath 'npm' }
    $uv = Get-CommandPath 'uv'
    $venvPython = Join-Path $Root '.venv\Scripts\python.exe'

    # --- 1. Cong cu bat buoc -----------------------------------------------
    if ($null -eq $node) {
        [void]$problems.Add('Thieu Node.js: cai Node 22+ roi mo lai terminal (kiem tra: node --version)')
    } else {
        $probe = Invoke-Native -FilePath $node -Arguments @('--version') -Quiet
        Write-Ok "node: $node ($($probe.Output -join ' '))"
    }

    if ($null -eq $npm) {
        [void]$problems.Add('Thieu npm: cai Node 22+ (kem npm) roi mo lai terminal (kiem tra: npm --version)')
    } else {
        $probe = Invoke-Native -FilePath $npm -Arguments @('--version') -Quiet
        Write-Ok "npm: $npm ($($probe.Output -join ' '))"
    }

    if ($null -eq $uv) {
        [void]$problems.Add('Thieu uv: cai uv (https://docs.astral.sh/uv/) roi mo lai terminal (kiem tra: uv --version)')
    } else {
        $probe = Invoke-Native -FilePath $uv -Arguments @('--version') -Quiet
        Write-Ok "uv: $uv ($($probe.Output -join ' '))"
    }

    # --- 2. File bat buoc ---------------------------------------------------
    foreach ($rel in $RequiredFiles) {
        $full = Join-Path $Root $rel
        if (Test-Path -LiteralPath $full) {
            Write-Ok "co file $rel"
        } else {
            [void]$problems.Add("Thieu file $rel (repo chua day du?)")
        }
    }

    # --- 3. Python + dependency backend ------------------------------------
    if ($null -ne $uv) {
        $pyProbe = Invoke-Native -FilePath $uv -Arguments @('python', 'find', '3.13') -Quiet
        if ($pyProbe.Code -eq 0) {
            Write-Ok "Python 3.13: $($pyProbe.Output -join ' ')"
        } else {
            [void]$problems.Add('Thieu Python 3.13 cho du an: chay `uv python install 3.13`')
        }
    }

    $venvReady = $false
    if (Test-Path -LiteralPath $venvPython) {
        $import = Invoke-Native -FilePath $venvPython -Arguments @('-c', 'import fastapi, uvicorn') -Quiet
        $venvReady = ($import.Code -eq 0)
    }
    if ($venvReady) {
        Write-Ok "dependency backend da cai (.venv co fastapi + uvicorn)"
    } else {
        [void]$problems.Add('Thieu dependency backend: chay `uv sync` (hoac dev.ps1 khong kem -NoInstall)')
    }

    # --- 4. Dependency frontend -------------------------------------------
    $viteBin = Join-Path $Root 'node_modules\vite\bin\vite.js'
    $nodeModulesReady = Test-Path -LiteralPath $viteBin
    if ($nodeModulesReady) {
        Write-Ok "dependency frontend da cai (node_modules co vite)"
    } else {
        [void]$problems.Add('Thieu dependency frontend: chay `npm install` (hoac dev.ps1 khong kem -NoInstall)')
    }

    # --- 5. Cong 8000/5173 con trong --------------------------------------
    foreach ($entry in @(@{ Port = $BackendPort; Label = 'backend' }, @{ Port = $FrontendPort; Label = 'frontend' })) {
        if (Test-PortFree -Port $entry.Port) {
            Write-Ok "cong $($entry.Port) ($($entry.Label)) dang trong"
        } else {
            [void]$problems.Add("cong $($entry.Port) ($($entry.Label)) dang ban: dung tien trinh cu tren cong do roi chay lai")
        }
    }

    # --- 6. Cai dependency con thieu (chi khi duoc phep) -------------------
    if ($problems.Count -gt 0 -and $AllowInstall -and (-not $venvReady) -and $null -ne $uv) {
        Write-Step 'Cai dependency backend con thieu: uv sync (dung -NoInstall de chan buoc mang nay)'
        $sync = Invoke-Native -FilePath $uv -Arguments @('sync')
        if ($sync.Code -eq 0) {
            $import = Invoke-Native -FilePath $venvPython -Arguments @('-c', 'import fastapi, uvicorn') -Quiet
            if ($import.Code -eq 0) {
                $venvReady = $true
                [void]$problems.Remove('Thieu dependency backend: chay `uv sync` (hoac dev.ps1 khong kem -NoInstall)')
                Write-Ok 'uv sync xong: dependency backend da san sang'
            }
        } else {
            Write-Bad "uv sync that bai (exit $($sync.Code))"
        }
    }
    if ($problems.Count -gt 0 -and $AllowInstall -and (-not $nodeModulesReady) -and $null -ne $npm) {
        Write-Step 'Cai dependency frontend con thieu: npm install (dung -NoInstall de chan buoc mang nay)'
        $install = Invoke-Native -FilePath $npm -Arguments @('install')
        if ($install.Code -eq 0 -and (Test-Path -LiteralPath $viteBin)) {
            $nodeModulesReady = $true
            [void]$problems.Remove('Thieu dependency frontend: chay `npm install` (hoac dev.ps1 khong kem -NoInstall)')
            Write-Ok 'npm install xong: dependency frontend da san sang'
        } else {
            Write-Bad "npm install that bai (exit $($install.Code))"
        }
    }

    return @{
        Problems = $problems
        Node     = $node
        Npm      = $npm
        Uv       = $uv
        VenvPython = $venvPython
    }
}

function Show-Problems {
    param([System.Collections.Generic.List[string]]$Problems)
    if ($Problems.Count -eq 0) { return }
    Write-Bad "Vi pham dieu kien tien quyet ($($Problems.Count)):"
    foreach ($problem in $Problems) { Write-Host "  - $problem" }
}

function Join-Arguments {
    <#
        Ghep danh sach doi so thanh mot chuoi lenh. Doi so co khoang trang / dau
        nhay duoc bao quanh bang dau nhay kep (Start-Process -ArgumentList khong
        tu dong quote, nen can lam ro thay duong dan co khoang trang nhu npm.cmd).
    #>
    param([string[]]$Arguments)
    $parts = foreach ($arg in $Arguments) {
        if ($arg -match '[\s"]') {
            '"' + ($arg -replace '"', '""') + '"'
        } else {
            $arg
        }
    }
    return ($parts -join ' ')
}

function Start-DevServer {
    param(
        [string]$Label,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$OutLog,
        [string]$ErrLog
    )
    # PowerShell-native: Start-Process -PassThru tra ve doi tuong Process => giu PID
    # de hien thi va de dung DUNG cay tien trinh do script nay mo.
    $process = Start-Process -FilePath $FilePath -ArgumentList (Join-Arguments -Arguments $Arguments) `
        -WorkingDirectory $Root -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
    Write-Ok "$Label da mo: PID=$($process.Id)  log=$OutLog"
    return $process
}

function Test-ProcessAlive {
    param([System.Diagnostics.Process]$Process)
    if ($null -eq $Process) { return $false }
    try {
        $Process.Refresh()
        return (-not $Process.HasExited)
    } catch {
        return $false
    }
}

function Show-LogTail {
    param([string]$Path, [int]$Lines = 15)
    if (-not (Test-Path -LiteralPath $Path)) { return }
    Write-Step "--- cuoi log $Path ---"
    foreach ($line in (Get-Content -LiteralPath $Path -Tail $Lines -ErrorAction SilentlyContinue)) {
        Write-Host "       $line"
    }
}

function Wait-HttpOk {
    param([string]$Url, [int]$TimeoutSeconds = 40)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) { return $true }
        } catch {
            Start-Sleep -Milliseconds 400
        }
    }
    return $false
}

function Stop-DevProcess {
    param([System.Diagnostics.Process]$Process, [string]$Label)
    if ($null -eq $Process) { return }
    if (-not (Test-ProcessAlive -Process $Process)) {
        Write-Step "$Label (PID=$($Process.Id)) da tu thoat."
        return
    }
    # Chi dung dung cay tien trinh do script nay mo (/T) — khong dung tien trinh khac.
    [void](Invoke-Native -FilePath 'taskkill.exe' -Arguments @('/PID', "$($Process.Id)", '/T', '/F') -Quiet)
    if (Test-ProcessAlive -Process $Process) {
        Write-Warn "$Label (PID=$($Process.Id)) chua dung han"
    } else {
        Write-Step "$Label (PID=$($Process.Id)) da dung."
    }
}

# ============================================================================
# Main
# ============================================================================
Write-Host '=== Vu Hoc AI Radar v1.0 — dev localhost (chi 127.0.0.1) ==='
Write-Step "Repo: $Root"
Write-Step ("Mode: " + $(if ($Check) { 'CHECK' } else { 'RUN' }))

$backendProcess = $null
$frontendProcess = $null
$exitCode = 1

try {
    $preflight = Invoke-Preflight -AllowInstall:(-not $NoInstall)
    $problems = $preflight.Problems

    Show-EnvTemplateStatus -TemplatePath (Join-Path $Root '.env.example')

    if ($problems.Count -gt 0) {
        Show-Problems -Problems $problems
        Write-Bad 'Tien quyet chua du — khong khoi dong server.'
        if ($Check) { Write-Step 'Check muc dich: bao loi ro rang, khong tu y cai dat.' }
        $exitCode = 1
    } elseif ($Check) {
        Write-Ok "CHECK OK: ${BackendPort}/127.0.0.1 va ${FrontendPort}/127.0.0.1 san sang khoi dong."
        $exitCode = 0
    } else {
        # --- Migration idempotent truoc khi mo server -----------------------
        Write-Step 'Chay migration idempotent: uv run --no-sync python -m backend.app.migrate'
        $migrate = Invoke-Native -FilePath $preflight.Uv `
            -Arguments @('run', '--no-sync', 'python', '-m', 'backend.app.migrate')
        if ($migrate.Code -ne 0) {
            Write-Bad "Migration that bai (exit $($migrate.Code)) — schema chua san sang."
            $exitCode = 1
        } else {
            Write-Ok 'Migration OK (idempotent, khong xoa du lieu).'

            if (-not (Test-Path -LiteralPath $LogsDir)) {
                [void](New-Item -ItemType Directory -Path $LogsDir -Force)
            }

            $comspec = $env:ComSpec
            if ([string]::IsNullOrWhiteSpace($comspec)) { $comspec = Join-Path $env:SystemRoot 'System32\cmd.exe' }

            $backendProcess = Start-DevServer -Label 'backend' -FilePath $preflight.Uv `
                -Arguments @('run', '--no-sync', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', "$BackendPort") `
                -OutLog (Join-Path $LogsDir 'backend.out.log') -ErrLog (Join-Path $LogsDir 'backend.err.log')

            $frontendProcess = Start-DevServer -Label 'frontend' -FilePath $comspec `
                -Arguments @('/c', $preflight.Npm, 'run', 'dev', '--', '--host', '127.0.0.1', '--port', "$FrontendPort") `
                -OutLog (Join-Path $LogsDir 'frontend.out.log') -ErrLog (Join-Path $LogsDir 'frontend.err.log')

            $backendUrl = "http://127.0.0.1:$BackendPort/api/health"
            $frontendUrl = "http://127.0.0.1:$FrontendPort/"
            Write-Step "Cho backend tra HTTP tai $backendUrl ..."
            $backendUp = Wait-HttpOk -Url $backendUrl -TimeoutSeconds 40
            Write-Step "Cho frontend tra HTTP tai $frontendUrl ..."
            $frontendUp = Wait-HttpOk -Url $frontendUrl -TimeoutSeconds 40

            if (-not $backendUp) {
                Write-Bad 'Backend khong tra HTTP kip thoi.'
                Show-LogTail -Path (Join-Path $LogsDir 'backend.err.log')
                Show-LogTail -Path (Join-Path $LogsDir 'backend.out.log')
                $exitCode = 1
            } elseif (-not $frontendUp) {
                Write-Bad 'Vite khong tra HTTP kip thoi.'
                Show-LogTail -Path (Join-Path $LogsDir 'frontend.err.log')
                Show-LogTail -Path (Join-Path $LogsDir 'frontend.out.log')
                $exitCode = 1
            } else {
                Write-Ok "Backend UP  -> $backendUrl  (PID=$($backendProcess.Id))"
                Write-Ok "Frontend UP -> $frontendUrl (PID=$($frontendProcess.Id))"
                Write-Host ''
                Write-Host 'PID dang chay (script nay se dung dung cac PID nay khi ket thuc):'
                Write-Host "  backend : $($backendProcess.Id)"
                Write-Host "  frontend: $($frontendProcess.Id)"
                Write-Host ''

                if ($AutoStopSeconds -gt 0) {
                    Write-Step "Che do kiem thu tu dong: tu dung sau $AutoStopSeconds giay."
                    $deadline = (Get-Date).AddSeconds($AutoStopSeconds)
                    $exitCode = 0
                    while ((Get-Date) -lt $deadline) {
                        Start-Sleep -Milliseconds 500
                        if (-not (Test-ProcessAlive -Process $backendProcess)) {
                            Write-Bad 'Backend thoat som.'; Show-LogTail -Path (Join-Path $LogsDir 'backend.err.log'); $exitCode = 1; break
                        }
                        if (-not (Test-ProcessAlive -Process $frontendProcess)) {
                            Write-Bad 'Frontend thoat som.'; Show-LogTail -Path (Join-Path $LogsDir 'frontend.err.log'); $exitCode = 1; break
                        }
                    }
                } else {
                    Write-Host 'Dang chay. Nhan Ctrl+C de dung hai server (chi dung PID do script nay mo).'
                    $exitCode = 0
                    while ($true) {
                        Start-Sleep -Milliseconds 500
                        if (-not (Test-ProcessAlive -Process $backendProcess)) {
                            Write-Bad 'Backend thoat.'; Show-LogTail -Path (Join-Path $LogsDir 'backend.err.log'); $exitCode = 1; break
                        }
                        if (-not (Test-ProcessAlive -Process $frontendProcess)) {
                            Write-Bad 'Frontend thoat.'; Show-LogTail -Path (Join-Path $LogsDir 'frontend.err.log'); $exitCode = 1; break
                        }
                    }
                }
            }
        }
    }
} finally {
    Stop-DevProcess -Process $frontendProcess -Label 'frontend'
    Stop-DevProcess -Process $backendProcess -Label 'backend'
    Write-Step "Ket thuc (exit $exitCode)."
}

exit $exitCode
