# install_vosk_model.ps1
# Downloads and extracts the Vosk small English model into ./models
# Usage (PowerShell):
#   .\install_vosk_model.ps1

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$modelsDir = Join-Path $scriptDir "models"
$modelName = 'vosk-model-small-en-us-0.15'
$zipUrl = "https://alphacephei.com/vosk/models/$modelName.zip"
$zipPath = Join-Path $env:TEMP "$modelName.zip"
$targetDir = Join-Path $modelsDir $modelName

if (Test-Path $targetDir) {
    Write-Host "Vosk model already exists at: $targetDir"
    exit 0
}

if (-not (Test-Path $modelsDir)) {
    New-Item -ItemType Directory -Path $modelsDir | Out-Null
}

Write-Host "Downloading Vosk model from: $zipUrl"
try {
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing -Verbose
} catch {
    Write-Error "Download failed: $_"
    exit 1
}

Write-Host "Extracting to $modelsDir (this may take several minutes)"
try {
    Expand-Archive -Path $zipPath -DestinationPath $modelsDir -Force
} catch {
    Write-Error "Extraction failed: $_"
    exit 1
}

Remove-Item $zipPath -Force
Write-Host "Model installed to: $targetDir"
Write-Host "Set the environment variable VOSK_MODEL_PATH to: $targetDir"
Write-Host "Example (PowerShell): $env:VOSK_MODEL_PATH = '$targetDir' ; $env:PATH"
