$ErrorActionPreference = "Stop"
$rootScript = Join-Path $PSScriptRoot "..\..\deploy_floci.ps1"
& $rootScript
if ($LASTEXITCODE -ne 0) {
    throw "Full Floci deployment failed with exit code $LASTEXITCODE."
}
