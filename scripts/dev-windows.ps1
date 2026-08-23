$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$apiDir = Join-Path $projectRoot "api"
$webDir = Join-Path $projectRoot "web"
$venvDir = Join-Path $apiDir ".venv"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"
$dataDir = Join-Path $projectRoot "data"
$processStatePath = Join-Path $dataDir ".dev-processes.json"
$apiOutputLog = Join-Path $dataDir "dev-api.log"
$apiErrorLog = Join-Path $dataDir "dev-api-error.log"
$webOutputLog = Join-Path $dataDir "dev-web.log"
$webErrorLog = Join-Path $dataDir "dev-web-error.log"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "未找到 Python。请先安装 Python 3.12。"
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "未找到 npm。请先安装 Node.js 22。"
}

function Find-AvailablePort([int]$StartPort) {
    foreach ($port in $StartPort..($StartPort + 99)) {
        # Next.js listens on IPv6 (::) by default, so an IPv4-only bind check can
        # incorrectly report an occupied port as available.
        if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
            continue
        }
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
        try {
            $listener.Start()
            return $port
        } catch {
            # Try the next port.
        } finally {
            $listener.Stop()
        }
    }
    throw "从端口 $StartPort 开始连续 100 个端口均被占用。"
}

function Get-DescendantProcessIds([int]$ProcessId, $Processes) {
    foreach ($child in $Processes | Where-Object { $_.ParentProcessId -eq $ProcessId }) {
        $child.ProcessId
        Get-DescendantProcessIds $child.ProcessId $Processes
    }
}

function Stop-ProcessTree([int]$ProcessId) {
    $processes = @(Get-CimInstance Win32_Process)
    $descendantIds = @(Get-DescendantProcessIds $ProcessId $processes)

    # Stop the launcher first so it cannot respawn a child while the tree is being removed.
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    if ($descendantIds.Count -gt 0) {
        Stop-Process -Id $descendantIds -Force -ErrorAction SilentlyContinue
    }
}

function Stop-ExistingDevProcesses {
    $stoppedWeb = $false
    $stoppedProcessIds = [System.Collections.Generic.HashSet[int]]::new()

    if (Test-Path $processStatePath) {
        try {
            $state = Get-Content -Raw $processStatePath | ConvertFrom-Json
            if ($state.projectRoot -eq $projectRoot) {
                foreach ($entry in @(
                    @{ Id = [int]$state.apiProcessId; Type = "API" },
                    @{ Id = [int]$state.webProcessId; Type = "Web" }
                )) {
                    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($entry.Id)" -ErrorAction SilentlyContinue
                    if ($process -and $process.CommandLine -like "*$projectRoot*" -and $process.CommandLine -like "*Furigana $($entry.Type) (dev)*") {
                        Write-Host "正在停止原有的 Furigana $($entry.Type) 开发进程（PID $($entry.Id)）..."
                        Stop-ProcessTree $entry.Id
                        [void]$stoppedProcessIds.Add($entry.Id)
                        if ($entry.Type -eq "Web") { $stoppedWeb = $true }
                    }
                }
            }
        } catch {
            Write-Warning "无法读取旧的开发进程状态，将改用进程命令行识别：$($_.Exception.Message)"
        } finally {
            Remove-Item -LiteralPath $processStatePath -Force -ErrorAction SilentlyContinue
        }
    }

    # Compatibility cleanup for processes created before the state file was introduced.
    # Launchers are stopped first; remaining services are then removed in batches to avoid
    # a reload process spawning a replacement worker during cleanup.
    $legacyLaunchers = @(Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $PID -and
        $_.Name -in @("powershell.exe", "pwsh.exe") -and
        $_.CommandLine -like "*$projectRoot*" -and
        $_.CommandLine -like "*Furigana *(dev)*"
    })
    foreach ($process in $legacyLaunchers) {
        if (Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue) {
            Write-Host "正在清理遗留的 Furigana 开发窗口（PID $($process.ProcessId)）..."
            if ($process.CommandLine -like "*Furigana Web (dev)*") { $stoppedWeb = $true }
            Stop-ProcessTree $process.ProcessId
        }
    }

    foreach ($attempt in 1..3) {
        $legacyServices = @(Get-CimInstance Win32_Process | Where-Object {
            $_.ProcessId -ne $PID -and (
                ($_.Name -eq "node.exe" -and $_.CommandLine -like "*$webDir\node_modules*" -and $_.CommandLine -match "next.*dev") -or
                ($_.Name -eq "python.exe" -and (
                    ($_.CommandLine -like "*$projectRoot*" -and $_.CommandLine -like "*uvicorn app.main:app*") -or
                    ($_.CommandLine -like "*$pythonExe*" -and $_.CommandLine -like "*multiprocessing.spawn*")
                ))
            )
        })
        if ($legacyServices.Count -eq 0) { break }

        $serviceIds = @($legacyServices.ProcessId | Sort-Object -Unique)
        foreach ($process in $legacyServices) {
            Write-Host "正在清理遗留的 Furigana 开发服务（PID $($process.ProcessId)）..."
            if ($process.Name -eq "node.exe") { $stoppedWeb = $true }
        }
        Stop-Process -Id $serviceIds -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 250
    }

    if ($stoppedWeb) {
        Start-Sleep -Milliseconds 500
        $nextCache = Join-Path $webDir ".next"
        if (Test-Path $nextCache) {
            Write-Host "正在清理旧的 Next.js 开发缓存..."
            Remove-Item -LiteralPath $nextCache -Recurse -Force
        }
    }
}

if (-not (Test-Path (Join-Path $projectRoot ".env"))) {
    Copy-Item (Join-Path $projectRoot ".env.example") (Join-Path $projectRoot ".env")
    Write-Host "已从 .env.example 创建 .env。"
}
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
Stop-ExistingDevProcesses
Start-Sleep -Milliseconds 750

if (-not (Test-Path $pythonExe)) {
    Write-Host "正在创建 Python 虚拟环境..."
    python -m venv $venvDir
}

Write-Host "正在检查后端依赖..."
& $pythonExe -m pip install -r (Join-Path $apiDir "requirements-dev.txt")

Write-Host "正在检查前端依赖..."
Push-Location $webDir
try { npm install } finally { Pop-Location }

$webPort = Find-AvailablePort 3000
$apiPort = Find-AvailablePort 8000
$webUrl = "http://localhost:$webPort"
$apiUrl = "http://localhost:$apiPort"
$apiHealthUrl = "http://127.0.0.1:$apiPort/health"
$nodeExe = (Get-Command node.exe -ErrorAction Stop).Source
$nextCli = Join-Path $webDir "node_modules\next\dist\bin\next"
$envFile = Join-Path $projectRoot ".env"
$dbPath = Join-Path $dataDir "furigana.sqlite3"

Remove-Item -LiteralPath @($apiOutputLog, $apiErrorLog, $webOutputLog, $webErrorLog) -Force -ErrorAction SilentlyContinue

Write-Host "正在启动开发服务器（修改源码会自动更新）..."
Write-Host "Web: $webUrl"
Write-Host "API: $apiUrl"
Write-Host "日志: $apiOutputLog / $webOutputLog"

$previousDbPath = $env:DB_PATH
$previousCorsOrigins = $env:CORS_ORIGINS
try {
    $env:DB_PATH = $dbPath
    $env:CORS_ORIGINS = $webUrl
    $apiProcess = Start-Process $pythonExe `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--env-file", $envFile, "--reload", "--port", $apiPort) `
        -WorkingDirectory $apiDir -WindowStyle Hidden `
        -RedirectStandardOutput $apiOutputLog -RedirectStandardError $apiErrorLog -PassThru
} finally {
    $env:DB_PATH = $previousDbPath
    $env:CORS_ORIGINS = $previousCorsOrigins
}

$previousApiBaseUrl = $env:NEXT_PUBLIC_API_BASE_URL
try {
    $env:NEXT_PUBLIC_API_BASE_URL = $apiUrl
    $webProcess = Start-Process $nodeExe `
        -ArgumentList @($nextCli, "dev", "-p", $webPort) `
        -WorkingDirectory $webDir -WindowStyle Hidden `
        -RedirectStandardOutput $webOutputLog -RedirectStandardError $webErrorLog -PassThru
} finally {
    $env:NEXT_PUBLIC_API_BASE_URL = $previousApiBaseUrl
}
@{
    version = 1
    projectRoot = $projectRoot
    apiProcessId = $apiProcess.Id
    webProcessId = $webProcess.Id
} | ConvertTo-Json | Set-Content -LiteralPath $processStatePath -Encoding utf8

$deadline = (Get-Date).AddMinutes(2)
do {
    try {
        $webReady = (Invoke-WebRequest -Uri $webUrl -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
    } catch {
        $webReady = $false
    }
    try {
        # Uvicorn binds to IPv4 by default; using localhost can resolve to ::1 first on Windows.
        $apiReady = (Invoke-WebRequest -Uri $apiHealthUrl -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
    } catch {
        $apiReady = $false
    }

    if (-not ($webReady -and $apiReady)) { Start-Sleep -Seconds 1 }
} while (-not ($webReady -and $apiReady) -and (Get-Date) -lt $deadline)

if ($webReady -and $apiReady) {
    Write-Host "开发环境已启动：$webUrl（API: $apiUrl）"
    Start-Process $webUrl
} else {
    $failedServices = @()
    if (-not $webReady) { $failedServices += "Web ($webUrl)" }
    if (-not $apiReady) { $failedServices += "API ($apiHealthUrl)" }
    Stop-ExistingDevProcesses
    throw "开发环境启动失败：$($failedServices -join '、') 未就绪。请查看 $apiErrorLog 和 $webErrorLog。"
}
