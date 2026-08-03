# Start the AI Voice Assistant server and open the web UI.
# Run this from PowerShell in the project root.

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root

$venvPython = Join-Path $root "assistant\venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Error "Virtual environment Python not found: $venvPython"
    Pop-Location
    exit 1
}

function Test-PortAvailable {
    param([int]$Port)
    $result = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue
    return -not $result.TcpTestSucceeded
}

$port = 8000
if (-not (Test-PortAvailable -Port $port)) {
    Write-Host "Port $port is occupied. Trying port 8001..."
    $port = 8001
    if (-not (Test-PortAvailable -Port $port)) {
        Write-Error "Ports 8000 and 8001 are both occupied. Please free one and try again."
        Pop-Location
        exit 1
    }
}

$arguments = @(
    '-m',
    'uvicorn',
    'assistant.server.main:app',
    '--host',
    '127.0.0.1',
    '--port',
    $port.ToString(),
    '--reload'
)

Write-Host "Starting backend server on port $port in a new window..."
Start-Process -FilePath $venvPython -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Normal

$uiUrl = "http://127.0.0.1:$port/"
$maxAttempts = 15
$attempt = 0
$ready = $false
while ($attempt -lt $maxAttempts -and -not $ready) {
    Start-Sleep -Seconds 1
    try {
        $response = Invoke-WebRequest -Uri $uiUrl -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        # ignore and retry
    }
    $attempt++
}

if (-not $ready) {
    Write-Warning "Server did not respond within $maxAttempts seconds. Opening browser anyway."
}

Write-Host "Opening web UI in your default browser..."
Start-Process $uiUrl

Pop-Location
