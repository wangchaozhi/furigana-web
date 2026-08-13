$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$apiDir = Join-Path $projectRoot "api"
$webDir = Join-Path $projectRoot "web"
$venvDir = Join-Path $apiDir ".venv"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"
$dataDir = Join-Path $projectRoot "data"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "未找到 Python。请先安装 Python 3.12。"
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "未找到 npm。请先安装 Node.js 22。"
}

function Find-AvailablePort([int]$StartPort) {
    foreach ($port in $StartPort..($StartPort + 99)) {
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

if (-not (Test-Path (Join-Path $projectRoot ".env"))) {
    Copy-Item (Join-Path $projectRoot ".env.example") (Join-Path $projectRoot ".env")
    Write-Host "已从 .env.example 创建 .env。"
}
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

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

$apiCommand = @"
`$Host.UI.RawUI.WindowTitle = 'Furigana API (dev)'
Set-Location '$apiDir'
`$env:DB_PATH = '$($dataDir.Replace("'", "''"))\furigana.sqlite3'
`$env:CORS_ORIGINS = '$webUrl'
& '$pythonExe' -m uvicorn app.main:app --env-file '$projectRoot\.env' --reload --port $apiPort
"@
$webCommand = @"
`$Host.UI.RawUI.WindowTitle = 'Furigana Web (dev)'
Set-Location '$webDir'
`$env:NEXT_PUBLIC_API_BASE_URL = '$apiUrl'
npm run dev -- -p $webPort
"@

Write-Host "正在启动开发服务器（修改源码会自动更新）..."
Write-Host "Web: $webUrl"
Write-Host "API: $apiUrl"
Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $apiCommand)
Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $webCommand)

$deadline = (Get-Date).AddMinutes(2)
do {
    try {
        $webReady = (Invoke-WebRequest -Uri $webUrl -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
    } catch {
        $webReady = $false
    }
    if (-not $webReady) { Start-Sleep -Seconds 1 }
} while (-not $webReady -and (Get-Date) -lt $deadline)

if ($webReady) {
    Write-Host "开发环境已启动：$webUrl"
    Start-Process $webUrl
} else {
    Write-Warning "页面尚未就绪，请查看新打开的 API 和 Web 窗口。"
}
