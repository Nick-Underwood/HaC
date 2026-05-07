param(
    [string]$WorkflowDir = ".forgejo/workflows",
    [string]$OutputPath = "development/service-catalog/data/services.inventory.json"
)

$ErrorActionPreference = "Stop"

function ConvertTo-RelativePath {
    param([string]$Path)

    return $Path.Substring((Get-Location).Path.Length + 1) -replace '\\','/'
}

function Get-ComposePathFromWorkflow {
    param([string]$Raw)

    $workingDirectorySearch = Select-String -InputObject $Raw -Pattern 'working-directory:\s+"\./(Docker-(Critical|NonCritical)/[^\r\n"'']+)"'
    $composeFileSearch = Select-String -InputObject $Raw -Pattern 'docker compose[^\r\n]+-f\s+([^\s"''`]+\.ya?ml)'
    $workingDirectory = $null
    $composeFile = $null

    if ($workingDirectorySearch.Matches.Count -gt 0) {
        $workingDirectory = $workingDirectorySearch.Matches[0].Groups[1].Value
    }

    if ($composeFileSearch.Matches.Count -gt 0) {
        $composeFile = $composeFileSearch.Matches[0].Groups[1].Value
    }

    if ($workingDirectory -and $composeFile) {
        return "$workingDirectory/$composeFile"
    }

    $composePaths = @(
        Select-String -InputObject $Raw -Pattern 'Docker-(Critical|NonCritical)/[^\r\n"'']+\.ya?ml' -AllMatches |
            ForEach-Object { $_.Matches } |
            ForEach-Object { $_.Value } |
            Select-Object -Unique
    )

    if ($composePaths.Count -ge 1) {
        return $composePaths[0]
    }

    if ($workingDirectory) {
        $composeFileFallbackSearch = Select-String -InputObject $Raw -Pattern '-f\s+([^\s"''`]+\.ya?ml)'
        if ($composeFileFallbackSearch.Matches.Count -gt 0) {
            $composeFileFallback = $composeFileFallbackSearch.Matches[0].Groups[1].Value
            return "$workingDirectory/$composeFileFallback"
        }
    }

    return $null
}

function Get-DomainFromComposePath {
    param([string]$ComposePath)

    $segments = $ComposePath -split '/'
    if ($segments.Count -lt 3) {
        return 'management'
    }

    $domain = switch ($segments[1]) {
        'Auth' { 'auth' }
        'Networking' { 'networking' }
        'Home' { 'home' }
        'Management' { 'management' }
        'Media' { 'media' }
        'Tools' { 'tools' }
        'Automation' { 'automation' }
        'Security' { 'security' }
        'Finance' { 'finance' }
        default { 'management' }
    }

    return $domain
}

function Get-DisplayName {
    param([string]$Id)

    $segments = ($Id -split '-') | ForEach-Object {
        if ($_.Length -gt 0) {
            $_.Substring(0, 1).ToUpper() + $_.Substring(1)
        }
    }

    return ($segments -join ' ')
}

$deployWorkflows = Get-ChildItem -Path $WorkflowDir -Filter "deploy-*.yml" -File
$services = @()

foreach ($workflow in $deployWorkflows) {
    $raw = Get-Content -LiteralPath $workflow.FullName -Raw
    $composePath = Get-ComposePathFromWorkflow -Raw $raw

    if (-not $composePath) {
        continue
    }

    $tier = if ($composePath.StartsWith("Docker-Critical/")) { "critical" } else { "noncritical" }
    $targetHost = if ($tier -eq "critical") { "hac-critical" } else { "hac-noncritical" }
    $domain = Get-DomainFromComposePath -ComposePath $composePath

    $base = [System.IO.Path]::GetFileNameWithoutExtension($workflow.Name)
    $id = $base -replace '^deploy-', ''
    $id = $id -replace '[^a-zA-Z0-9-]', '-'
    $id = $id.ToLower()

    $service = [pscustomobject][ordered]@{
        id = $id
        name = Get-DisplayName -Id $id
        tier = $tier
        host = $targetHost
        domain = $domain
        composePath = $composePath
        workflowPath = ConvertTo-RelativePath -Path $workflow.FullName
        owner = "unassigned"
        criticality = if ($tier -eq "critical") { "tier-2" } else { "tier-3" }
        rollbackClass = "stateless"
        dependencies = @()
        changeWindow = "off-peak"
        notes = "Generated from deploy workflow metadata; requires curation."
    }

    $services += $service
}

$deduped = $services | Sort-Object id -Unique

$doc = [ordered]@{
    schemaVersion = "1.0"
    generatedAt = (Get-Date).ToUniversalTime().ToString("o")
    services = $deduped
}

$targetDir = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}

$doc | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath

Write-Host "Generated inventory at $OutputPath with $($deduped.Count) services."
