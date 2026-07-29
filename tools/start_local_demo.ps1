param(
    [int]$BackendPort = 18000,
    [int]$FrontendPort = 15173
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $repoRoot 'logs\local'

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

foreach ($portValue in @($BackendPort, $FrontendPort)) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $portValue -ErrorAction SilentlyContinue
    if ($listener) {
        throw "Port $portValue is already used by PID $($listener[0].OwningProcess)."
    }
}

python -m py_compile (Join-Path $repoRoot 'tools\local_demo_backend.py')
if ($LASTEXITCODE -ne 0) { throw 'Demo backend syntax check failed.' }

$previousBackendPort = $env:LOCAL_DEMO_BACKEND_PORT
$env:LOCAL_DEMO_BACKEND_PORT = "$BackendPort"
try {
    $backendProcess = Start-Process `
        -FilePath 'python' `
        -ArgumentList @('tools\local_demo_backend.py') `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDir 'demo-backend.out.log') `
        -RedirectStandardError (Join-Path $logDir 'demo-backend.err.log') `
        -PassThru
} finally {
    $env:LOCAL_DEMO_BACKEND_PORT = $previousBackendPort
}

$previousTarget = $env:VITE_API_PROXY_TARGET
$env:VITE_API_PROXY_TARGET = "http://127.0.0.1:$BackendPort"
try {
    $frontendProcess = Start-Process `
        -FilePath 'pnpm.cmd' `
        -ArgumentList @('dev', '--host', '127.0.0.1', '--port', "$FrontendPort", '--strictPort') `
        -WorkingDirectory (Join-Path $repoRoot 'frontend') `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDir 'react-frontend.out.log') `
        -RedirectStandardError (Join-Path $logDir 'react-frontend.err.log') `
        -PassThru
} finally {
    $env:VITE_API_PROXY_TARGET = $previousTarget
}

$backendReady = $false
$frontendReady = $false
for ($attempt = 0; $attempt -lt 40; $attempt += 1) {
    if (-not $backendReady) {
        try {
            $response = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/" -TimeoutSec 2
            $backendReady = [bool]$response.message
        } catch { }
    }
    if (-not $frontendReady) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort/" -UseBasicParsing -TimeoutSec 2
            $frontendReady = $response.StatusCode -eq 200
        } catch { }
    }
    if ($backendReady -and $frontendReady) { break }
    Start-Sleep -Milliseconds 500
}

if (-not ($backendReady -and $frontendReady)) {
    Write-Output "Backend ready: $backendReady"
    Write-Output "Frontend ready: $frontendReady"
    Get-Content (Join-Path $logDir 'demo-backend.err.log') -Tail 30 -ErrorAction SilentlyContinue
    Get-Content (Join-Path $logDir 'react-frontend.err.log') -Tail 30 -ErrorAction SilentlyContinue
    exit 1
}

Write-Output "Backend PID: $($backendProcess.Id)"
Write-Output "Frontend PID: $($frontendProcess.Id)"
Write-Output "Frontend URL: http://127.0.0.1:$FrontendPort/"
Write-Output "Backend URL: http://127.0.0.1:$BackendPort/"
