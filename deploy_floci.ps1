$ErrorActionPreference = "Stop"

$terraformDirectory = Join-Path $PSScriptRoot "terraform"
$dockerfile = Join-Path $PSScriptRoot "Dockerfile"
$proxyDockerfile = Join-Path $PSScriptRoot "Dockerfile.proxy"
$proxyConfigTemplate = Join-Path $terraformDirectory "backend-proxy.conf.template"
$proxyConfig = Join-Path $terraformDirectory "backend-proxy.conf"
$redisVariableFile = Join-Path $terraformDirectory "floci.auto.tfvars.json"
$terraformCommand = Get-Command terraform -ErrorAction SilentlyContinue
if ($terraformCommand) {
    $terraform = $terraformCommand.Source
} else {
    $terraform = Join-Path $env:LOCALAPPDATA `
        "Microsoft\WinGet\Packages\Hashicorp.Terraform_Microsoft.Winget.Source_8wekyb3d8bbwe\terraform.exe"
    if (-not (Test-Path $terraform)) {
        throw "Terraform CLI was not found. Install Terraform or refresh the VS Code PATH."
    }
}

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "AWS CLI was not found."
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found."
}

function Read-SecretEnvironmentVariable {
    param(
        [string]$Name,
        [string]$Prompt,
        [int]$MinimumLength
    )

    $existingValue = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ($existingValue) {
        if ($existingValue.Length -lt $MinimumLength) {
            throw "$Name must be at least $MinimumLength characters. Update the environment variable and rerun."
        }
        return
    }

    while ($true) {
        $secureValue = Read-Host -AsSecureString "$Prompt (minimum $MinimumLength characters)"
        $pointer = [IntPtr]::Zero
        try {
            if ($secureValue.Length -lt $MinimumLength) {
                Write-Warning "$Name must be at least $MinimumLength characters. Please enter it again."
                continue
            }

            $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
            $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
            [Environment]::SetEnvironmentVariable($Name, $value, "Process")
        } finally {
            if ($pointer -ne [IntPtr]::Zero) {
                [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
            }
            if ($secureValue) {
                $secureValue.Dispose()
            }
            $value = $null
        }

        break
    }
}

$originalAccessKey = $env:AWS_ACCESS_KEY_ID
$originalSecretKey = $env:AWS_SECRET_ACCESS_KEY
$originalRegion = $env:AWS_DEFAULT_REGION
$originalDatabasePassword = $env:TF_VAR_database_password
$originalJwtSecret = $env:TF_VAR_jwt_secret_key
$originalRedisContainerIp = $env:TF_VAR_redis_container_ip

try {
    $env:AWS_ACCESS_KEY_ID = "test"
    $env:AWS_SECRET_ACCESS_KEY = "test"
    $env:AWS_DEFAULT_REGION = "us-east-1"
    $backendImageTag = Get-Date -Format "yyyyMMddHHmmssfff"
    Read-SecretEnvironmentVariable "TF_VAR_database_password" "Enter the PostgreSQL password (use the same value on future deployments)" 12
    Read-SecretEnvironmentVariable "TF_VAR_jwt_secret_key" "Enter a JWT secret (reuse it on future deployments)" 32

    Push-Location $terraformDirectory
    try {
        & $terraform init -input=false
        if ($LASTEXITCODE -ne 0) {
            throw "Terraform init failed with exit code $LASTEXITCODE."
        }

        $state = & $terraform state list
        if ($LASTEXITCODE -ne 0) {
            throw "Could not read Terraform state."
        }
        $bucketAddress = 'module.frontend.aws_s3_bucket.frontend'
        if ($state -notcontains $bucketAddress) {
            $bucketNames = & aws s3api list-buckets --query "Buckets[].Name" --output text --endpoint-url=http://localhost:4566 --region us-east-1
            if ($LASTEXITCODE -ne 0) {
                throw "Could not query Floci S3 buckets."
            }

            if (($bucketNames -split "\s+") -contains "speech-frontend") {
                & $terraform import -input=false $bucketAddress "speech-frontend"
                if ($LASTEXITCODE -ne 0) {
                    throw "Could not import the existing S3 frontend bucket into the root Terraform state."
                }

                & $terraform import -input=false module.frontend.aws_s3_bucket_website_configuration.frontend "speech-frontend"
                if ($LASTEXITCODE -ne 0) {
                    throw "Could not import the existing S3 website configuration."
                }

                $remoteKeys = & aws s3api list-objects-v2 --bucket speech-frontend --query "Contents[].Key" --output text --endpoint-url=http://localhost:4566 --region us-east-1
                if ($LASTEXITCODE -ne 0) {
                    throw "Could not list existing frontend objects in Floci S3."
                }
                $remoteKeyList = @($remoteKeys -split "\s+")
                $staticDirectory = Join-Path $PSScriptRoot "assistant\server\static"
                foreach ($file in Get-ChildItem $staticDirectory -File -Recurse) {
                    $relativeKey = $file.FullName.Substring($staticDirectory.Length).TrimStart("\").Replace("\", "/")
                    if ($remoteKeyList -contains $relativeKey) {
                        $objectAddress = 'module.frontend.aws_s3_object.frontend_files["{0}"]' -f $relativeKey
                        & $terraform import -input=false $objectAddress "speech-frontend/$relativeKey"
                        if ($LASTEXITCODE -ne 0) {
                            throw "Could not import existing frontend object '$relativeKey'."
                        }
                    }
                }
            }
        }

        & $terraform apply '-target=aws_ecr_repository.speech_backend' -auto-approve -input=false
        if ($LASTEXITCODE -ne 0) {
            throw "Targeted ECR Terraform apply failed with exit code $LASTEXITCODE."
        }

    } finally {
        Pop-Location
    }

    $image = "localhost:5100/speech-backend:$backendImageTag"
    & docker build --file $dockerfile --tag $image $PSScriptRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Backend Docker build failed with exit code $LASTEXITCODE."
    }
    & docker push $image
    if ($LASTEXITCODE -ne 0) {
        throw "Backend Docker push failed with exit code $LASTEXITCODE."
    }

    Push-Location $terraformDirectory
    try {
        & $terraform apply '-target=aws_elasticache_cluster.redis' -auto-approve -input=false
        if ($LASTEXITCODE -ne 0) {
            throw "Could not provision Floci ElastiCache before resolving its Docker bridge address."
        }

        $redisContainer = $null
        $redisContainerIp = $null
        $redisQueryError = $null
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            $previousErrorActionPreference = $ErrorActionPreference
            try {
                $ErrorActionPreference = "Continue"
                $runningContainers = & docker ps --filter "name=valkey-speech-redis" --filter "status=running" --format "{{.Names}}" 2>&1
                $dockerExitCode = $LASTEXITCODE
            } finally {
                $ErrorActionPreference = $previousErrorActionPreference
            }
            if ($dockerExitCode -ne 0) {
                $redisQueryError = ($runningContainers -join " ").Trim()
                Start-Sleep -Seconds 2
                continue
            }
            $redisContainer = $runningContainers | Select-Object -First 1
            if ($redisContainer) {
                try {
                    $redisContainerIp = & docker inspect --format "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" $redisContainer
                    if ($LASTEXITCODE -ne 0) {
                        $redisContainerIp = $null
                    }
                } catch {
                    $redisContainerIp = $null
                }
                if ($redisContainerIp -match '^\d{1,3}(\.\d{1,3}){3}$') {
                    break
                }
                $redisContainerIp = $null
            }
            Start-Sleep -Seconds 2
        }
        if (-not $redisContainer -or -not $redisContainerIp) {
            $failureDetail = if ($redisQueryError) { "Last Docker query error: $redisQueryError" } else { "No running cache container with a valid bridge IP was found." }
            throw "Floci ElastiCache container did not become ready within 120 seconds. $failureDetail"
        }
        $savedVariables = $null
        if (Test-Path $redisVariableFile) {
            $savedVariables = Get-Content $redisVariableFile -Raw | ConvertFrom-Json
        }
        $ollamaModel = $env:TF_VAR_ollama_model
        if (-not $ollamaModel -and $savedVariables) {
            $ollamaModel = $savedVariables.ollama_model
        }
        if (-not $ollamaModel) {
            $ollamaModel = "llama3.2"
        }
        @{
            redis_container_ip = $redisContainerIp
            backend_image_tag  = $backendImageTag
            ollama_model       = $ollamaModel
        } |
            ConvertTo-Json |
            Set-Content -Path $redisVariableFile -Encoding Ascii
        $env:TF_VAR_redis_container_ip = $redisContainerIp

        & $terraform apply -auto-approve -input=false
        if ($LASTEXITCODE -ne 0) {
            throw "Full Floci Terraform apply failed with exit code $LASTEXITCODE."
        }

        $backendContainer = $null
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            $runningContainers = & docker ps --filter "ancestor=$image" --filter "status=running" --format "{{.Names}}"
            if ($LASTEXITCODE -ne 0) {
                throw "Could not query running Floci ECS containers."
            }
            $backendContainer = $runningContainers | Select-Object -First 1
            if ($backendContainer) {
                break
            }
            Start-Sleep -Seconds 2
        }
        if (-not $backendContainer) {
            throw "The Floci ECS FastAPI container did not start within 120 seconds."
        }

        $taskIp = & docker inspect --format "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" $backendContainer
        if ($LASTEXITCODE -ne 0 -or $taskIp -notmatch '^\d{1,3}(\.\d{1,3}){3}$') {
            throw "Could not resolve the Floci ECS task's Docker bridge address."
        }

        $proxyConfiguration = (Get-Content $proxyConfigTemplate -Raw).Replace("__TASK_IP__", $taskIp)
        Set-Content -Path $proxyConfig -Value $proxyConfiguration -Encoding Ascii
        & docker build --file $proxyDockerfile --tag speech-backend-proxy:latest $PSScriptRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Could not build the local ECS backend proxy image."
        }

        $existingProxy = & docker ps -a --filter "name=^/speech-floci-backend-proxy$" --format "{{.Names}}"
        if ($LASTEXITCODE -ne 0) {
            throw "Could not check for an existing ECS backend proxy."
        }
        if ($existingProxy) {
            & docker rm --force speech-floci-backend-proxy
            if ($LASTEXITCODE -ne 0) {
                throw "Could not replace the existing ECS backend proxy container."
            }
        }

        & docker run --detach --name speech-floci-backend-proxy --restart unless-stopped `
            --network bridge --publish 127.0.0.1:8001:8001 `
            --mount "type=bind,source=$proxyConfig,target=/etc/nginx/conf.d/default.conf,readonly" `
            --entrypoint nginx speech-backend-proxy:latest -g "daemon off;"
        if ($LASTEXITCODE -ne 0) {
            throw "Could not start the localhost ECS backend proxy on port 8001."
        }

        $proxyHealthy = $false
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            try {
                $response = Invoke-WebRequest -Uri "http://127.0.0.1:8001/health" -TimeoutSec 3 -UseBasicParsing
                if ([int]$response.StatusCode -eq 200) {
                    $proxyHealthy = $true
                    break
                }
            } catch {
                Start-Sleep -Seconds 2
            }
        }
        if (-not $proxyHealthy) {
            throw "The ECS backend proxy did not pass its health check at http://127.0.0.1:8001."
        }

        Write-Output "ECS backend proxy ready at http://127.0.0.1:8001"
        & $terraform output
    } finally {
        Pop-Location
    }
} finally {
    $env:AWS_ACCESS_KEY_ID = $originalAccessKey
    $env:AWS_SECRET_ACCESS_KEY = $originalSecretKey
    $env:AWS_DEFAULT_REGION = $originalRegion
    $env:TF_VAR_database_password = $originalDatabasePassword
    $env:TF_VAR_jwt_secret_key = $originalJwtSecret
    $env:TF_VAR_redis_container_ip = $originalRedisContainerIp
}
