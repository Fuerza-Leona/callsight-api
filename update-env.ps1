# PowerShell script to fetch .env file from a specific branch of a secrets repo

param(
    [Parameter(Position=0, Mandatory=$false)]
    [string]$Branch
)

$SECRETS_REPO = "https://github.com/Fuerza-Leona/callsight-secrets.git"
$ENV_FILE_NAME = ".env.back"
$LOCAL_ENV_PATH = ".env"

function Show-Usage {
    Write-Host "Usage: .\update-env.ps1 -Branch <branch-name>"
    Write-Host "Examples:"
    Write-Host "  .\update-env.ps1 -Branch main"
    Write-Host "  .\update-env.ps1 -Branch staging"
    Write-Host "  .\update-env.ps1 -Branch feature/my-custom-branch"
}

if (-not $Branch) {
    Show-Usage
    exit 1
}

$OriginalDir = Get-Location
$TempDir = New-Item -ItemType Directory -Path ([System.IO.Path]::GetTempPath() + [System.Guid]::NewGuid().ToString())

Set-Location $TempDir

Write-Host "Fetching environment variables from branch '$Branch'..."

# Clone the specific branch (shallow)
git clone --depth 1 --branch $Branch $SECRETS_REPO .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to clone secrets repository."
    Set-Location $OriginalDir
    Remove-Item -Recurse -Force $TempDir
    exit 1
}

if (!(Test-Path $ENV_FILE_NAME)) {
    Write-Host "Error: Environment file '$ENV_FILE_NAME' not found in secrets repository."
    Set-Location $OriginalDir
    Remove-Item -Recurse -Force $TempDir
    exit 1
}

Copy-Item $ENV_FILE_NAME -Destination (Join-Path $OriginalDir $LOCAL_ENV_PATH) -Force

Set-Location $OriginalDir
Remove-Item -Recurse -Force $TempDir

Write-Host "Environment file updated successfully to $LOCAL_ENV_PATH!"