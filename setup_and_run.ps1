$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

try {
    $projectRoot = $PSScriptRoot
    $requirementsPath = Join-Path $projectRoot "requirements.txt"
    $appPath = Join-Path $projectRoot "crew_pdf_4agents.py"
    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

    if (-not (Test-Path $requirementsPath -PathType Leaf)) {
        throw "requirements.txt was not found in $projectRoot"
    }
    if (-not (Test-Path $appPath -PathType Leaf)) {
        throw "crew_pdf_4agents.py was not found in $projectRoot"
    }

    $pythonLauncher = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if (-not $pythonLauncher) {
        throw "Python Launcher was not found. Install Python 3.10 and enable the Python Launcher, then run this file again."
    }
    & $pythonLauncher.Source -3.10 --version
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.10 is required. Install Python 3.10, then run this file again."
    }

    if (-not (Test-Path $venvPython -PathType Leaf)) {
        Write-Host "`n[1/5] Creating Python virtual environment..."
        Invoke-CheckedCommand $pythonLauncher.Source @("-3.10", "-m", "venv", (Join-Path $projectRoot ".venv"))
    } else {
        $venvVersion = & $venvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        if ($LASTEXITCODE -ne 0 -or $venvVersion.Trim() -ne "3.10") {
            throw "The existing .venv must use Python 3.10. Back it up or rename it, then run setup again."
        }
    }

    Write-Host "`n[2/5] Installing Python packages from requirements.txt..."
    Invoke-CheckedCommand $venvPython @("-m", "pip", "install", "-r", $requirementsPath)

    $docker = Get-Command "docker.exe" -ErrorAction SilentlyContinue
    if (-not $docker) {
        throw "Docker CLI was not found. Install and start Docker Desktop, then run this file again."
    }
    & $docker.Source info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Engine is not running. Open Docker Desktop, wait until it is ready, then run this file again."
    }

    Write-Host "`n[3/5] Starting Ollama Docker container..."
    $containerState = & $docker.Source container inspect --format "{{.State.Running}}" ollama 2>$null
    if ($LASTEXITCODE -eq 0) {
        if (($containerState | Out-String).Trim() -ne "true") {
            Invoke-CheckedCommand $docker.Source @("start", "ollama")
        }
    } else {
        Invoke-CheckedCommand $docker.Source @(
            "run", "--detach",
            "--name", "ollama",
            "--restart", "unless-stopped",
            "--publish", "11434:11434",
            "--volume", "ollama:/root/.ollama",
            "ollama/ollama"
        )
    }

    $ollamaReady = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $null = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3
            $ollamaReady = $true
            break
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if (-not $ollamaReady) {
        throw "Ollama did not become ready at http://localhost:11434. Check the container with: docker logs ollama"
    }

    Write-Host "`n[4/5] Checking required Qwen models..."
    $models = @("qwen2.5:14b-instruct", "qwen2.5:7b-instruct")
    $installedModels = (Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 10).models |
        ForEach-Object { $_.name }
    foreach ($model in $models) {
        if ($installedModels -contains $model) {
            Write-Host "Already installed: $model"
        } else {
            Write-Host "`nDownloading $model. This may take a while..."
            Invoke-CheckedCommand $docker.Source @("exec", "ollama", "ollama", "pull", $model)
        }
    }

    Write-Host "`n[5/5] Starting the Local AI menu..."
    Push-Location $projectRoot
    try {
        & $venvPython $appPath
        if ($LASTEXITCODE -ne 0) {
            throw "crew_pdf_4agents.py exited with code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
} catch {
    Write-Host "`nSETUP ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
