$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "未找到 Docker。请先安装并启动 Docker Desktop。"
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker 服务未运行，请先启动 Docker Desktop。"
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "已从 .env.example 创建 .env。自动翻译需要在 .env 中填写 OPENAI_API_KEY。"
}

Write-Host "正在构建并启动 Furigana Studio..."
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw "Docker Compose 启动失败。" }

$deadline = (Get-Date).AddMinutes(5)
do {
    try {
        $webReady = (Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200
        $apiReady = (Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200
    } catch {
        $webReady = $false
        $apiReady = $false
    }
    if (-not ($webReady -and $apiReady)) { Start-Sleep -Seconds 2 }
} while (-not ($webReady -and $apiReady) -and (Get-Date) -lt $deadline)

if (-not ($webReady -and $apiReady)) {
    docker compose ps
    throw "服务未在 5 分钟内就绪，请运行 docker compose logs 查看日志。"
}

Write-Host "Furigana Studio 已启动：http://localhost:3000"
Start-Process "http://localhost:3000"
