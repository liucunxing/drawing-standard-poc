param(
    [int]$BackendPort = 18000,
    [int]$FrontendPort = 15173
)

$ErrorActionPreference = 'Stop'

foreach ($portValue in @($BackendPort, $FrontendPort)) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $portValue -ErrorAction SilentlyContinue
    if (-not $listener) { continue }
    $processId = $listener[0].OwningProcess
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$processId"
    $commandLine = [string]$process.CommandLine
    $isDemoBackend = $portValue -eq $BackendPort -and $commandLine.Contains('local_demo_backend.py')
    $isDemoFrontend = $portValue -eq $FrontendPort -and $commandLine.Contains('vite')
    if (-not ($isDemoBackend -or $isDemoFrontend)) {
        throw "Refusing to stop non-demo process PID $processId on port $portValue."
    }
    Stop-Process -Id $processId -Force
    Write-Output "Stopped demo process PID $processId on port $portValue"
}
