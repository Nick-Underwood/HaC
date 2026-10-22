param(
    [string]$TaskFile,
    [string]$ForgejoBaseUrl = "https://git.u-acres.com",
    [string]$Owner = "nicholas",
    [string]$Repo = "hac",
    [string]$Template = "task"
)

$ErrorActionPreference = "Stop"

if (-not $TaskFile) {
    throw "Provide -TaskFile with a markdown file containing unchecked tasks (e.g. '- [ ] ...')."
}

if (-not (Test-Path $TaskFile)) {
    throw "Task file not found: $TaskFile"
}

$token = $env:FORGEJO_TOKEN
if (-not $token) {
    throw "FORGEJO_TOKEN is not set. Set it in your environment and retry."
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$templatePath = Join-Path $repoRoot ".forgejo/issue_template/$Template.md"
if (-not (Test-Path $templatePath)) {
    throw "Template not found: $templatePath"
}
$templateBody = Get-Content -Path $templatePath -Raw

$stateDir = Join-Path $repoRoot ".vscode"
$stateFile = Join-Path $stateDir "adhd-task-sync-state.json"
if (-not (Test-Path $stateDir)) {
    New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
}

$state = @{}
if (Test-Path $stateFile) {
    $state = Get-Content -Path $stateFile -Raw | ConvertFrom-Json -AsHashtable
}
if (-not $state.ContainsKey("synced")) {
    $state["synced"] = @{}
}

$taskLines = Get-Content -Path $TaskFile | Where-Object { $_ -match '^\s*- \[ \] ' }
if (-not $taskLines) {
    Write-Host "No unchecked markdown tasks found in $TaskFile"
    exit 0
}

$headers = @{ Authorization = "token $token" }
$apiUrl = "$ForgejoBaseUrl/api/v1/repos/$Owner/$Repo/issues"
$created = 0

foreach ($line in $taskLines) {
    $taskText = ($line -replace '^\s*- \[ \] ', '').Trim()
    if (-not $taskText) {
        continue
    }

    $hash = [Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes($taskText))).ToLower()
    if ($state["synced"].ContainsKey($hash)) {
        continue
    }

    $title = "ADHD Task: $taskText"
    $body = "$templateBody`n`n## ADHD Task Source`n- File: $TaskFile`n- Task: $taskText"

    $payload = @{
        title = $title
        body = $body
    } | ConvertTo-Json -Depth 6

    $response = Invoke-RestMethod -Method Post -Uri $apiUrl -Headers $headers -ContentType "application/json" -Body $payload
    $state["synced"][$hash] = @{
        number = $response.number
        url = $response.html_url
        title = $title
        createdAt = (Get-Date).ToString("s")
    }
    $created++
    Write-Host "Created issue #$($response.number): $($response.html_url)"
}

$state | ConvertTo-Json -Depth 8 | Set-Content -Path $stateFile -Encoding UTF8
Write-Host "Sync complete. New issues created: $created"
