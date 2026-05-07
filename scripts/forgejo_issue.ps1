param(
    [string]$ForgejoBaseUrl = "https://git.u-acres.com",
    [string]$Owner = "nicholas",
    [string]$Repo = "hac",
    [ValidateSet("automation","bug","epic","feature","infra","security","task")]
    [string]$Template = "task",
    [string]$Title = "",
    [string]$BodyFile = "",
    [switch]$Create,
    [switch]$OpenDraft
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$templatePath = Join-Path $repoRoot ".forgejo/issue_template/$Template.md"

if (-not (Test-Path $templatePath)) {
    throw "Template not found: $templatePath"
}

$templateBody = Get-Content -Path $templatePath -Raw
$extraBody = ""
if ($BodyFile -and (Test-Path $BodyFile)) {
    $extraBody = "`n`n## Additional Notes`n" + (Get-Content -Path $BodyFile -Raw)
}

if (-not $Title) {
    $Title = Read-Host "Issue title"
}

$issueBody = $templateBody + $extraBody

if ($OpenDraft) {
    $encodedTitle = [uri]::EscapeDataString($Title)
    $encodedBody = [uri]::EscapeDataString($issueBody)
    $draftUrl = "$ForgejoBaseUrl/$Owner/$Repo/issues/new?title=$encodedTitle&template=$Template.md&body=$encodedBody"
    Start-Process $draftUrl | Out-Null
    Write-Host "Opened issue draft: $draftUrl"
}

if ($Create) {
    $token = $env:FORGEJO_TOKEN
    if (-not $token) {
        throw "FORGEJO_TOKEN is not set. Set it in your environment and retry with -Create."
    }

    $apiUrl = "$ForgejoBaseUrl/api/v1/repos/$Owner/$Repo/issues"
    $headers = @{ Authorization = "token $token" }
    $payload = @{
        title = $Title
        body = $issueBody
    } | ConvertTo-Json -Depth 6

    $response = Invoke-RestMethod -Method Post -Uri $apiUrl -Headers $headers -ContentType "application/json" -Body $payload
    Write-Host "Created issue #$($response.number): $($response.html_url)"
}

if (-not $Create -and -not $OpenDraft) {
    Write-Host "No action selected. Use -OpenDraft and/or -Create."
}
