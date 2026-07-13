# Publish jobs-applier to GitHub (run once after: gh auth login)
# Usage: .\scripts\publish-github.ps1 [-Username your-github-username]

param(
    [string]$Username = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

Write-Host "Checking GitHub CLI authentication..."
gh auth status
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Run 'gh auth login' first, then re-run this script."
    exit 1
}

if (-not $Username) {
    $Username = (gh api user --jq .login)
    Write-Host "Detected GitHub username: $Username"
}

# Update README badge URLs if still using placeholder
$readme = Get-Content README.md -Raw
$readme = $readme -replace "Ibrahim8325", $Username
$readme = $readme -replace "YOUR_USERNAME", $Username
Set-Content README.md $readme -NoNewline

if (git remote get-url origin 2>$null) {
    Write-Host "Remote 'origin' already exists. Pushing..."
    git push -u origin main
} else {
    Write-Host "Creating public repository and pushing..."
    gh repo create jobs-applier `
        --public `
        --source=. `
        --remote=origin `
        --description "Local job scraper and auto-applier (Apify + Playwright)" `
        --push
}

Write-Host ""
Write-Host "Repository published: https://github.com/$Username/jobs-applier"
Write-Host "CI will run automatically on push."
