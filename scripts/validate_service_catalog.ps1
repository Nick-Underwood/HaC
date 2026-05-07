param(
    [string]$CatalogPath = "development/service-catalog/data/services.catalog.json",
    [string]$SchemaPath = "development/service-catalog/schema/service-catalog.schema.json",
    [string]$WorkflowDir = ".forgejo/workflows"
)

$ErrorActionPreference = "Stop"

function Assert-FileExists {
    param([string]$Path, [string]$Label)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label not found: $Path"
    }
}

function Assert-Condition {
    param([bool]$Condition, [string]$Message)

    if (-not $Condition) {
        throw $Message
    }
}

function Get-RelativePath {
    param([string]$Path)

    return $Path.Substring((Get-Location).Path.Length + 1) -replace '\\','/'
}

function Get-DeployWorkflowEntries {
    param([string]$Path)

    Assert-FileExists -Path $Path -Label "Workflow directory"

    $entries = @()
    $deployWorkflows = Get-ChildItem -LiteralPath $Path -Filter "deploy-*.yml" -File | Sort-Object Name
    foreach ($workflow in $deployWorkflows) {
        $raw = Get-Content -LiteralPath $workflow.FullName -Raw
        $composeMatches = @()
        $workingDirectoryMatch = [regex]::Match($raw, 'working-directory:\s+"\./(Docker-(Critical|NonCritical)/[^\r\n"'']+)"')
        $composeFileMatch = [regex]::Match($raw, 'docker compose[^\r\n]+-f\s+([^\s"''`]+\.ya?ml)')

        if ($workingDirectoryMatch.Success -and $composeFileMatch.Success) {
            $composeMatches = @("$($workingDirectoryMatch.Groups[1].Value)/$($composeFileMatch.Groups[1].Value)")
        }

        if ($composeMatches.Count -eq 0) {
            $composeMatches = @(
                [regex]::Matches($raw, 'Docker-(Critical|NonCritical)/[^\r\n"'']+\.ya?ml') |
                    ForEach-Object { $_.Value } |
                    Select-Object -Unique
            )
        }

        if ($composeMatches.Count -eq 0) {
            $composeFileMatch = [regex]::Match($raw, '-f\s+([^\s"''`]+\.ya?ml)')

            if ($workingDirectoryMatch.Success -and $composeFileMatch.Success) {
                $composeMatches = @("$($workingDirectoryMatch.Groups[1].Value)/$($composeFileMatch.Groups[1].Value)")
            }
        }

        Assert-Condition ($composeMatches.Count -ge 1) "Deploy workflow missing compose path reference: $(Get-RelativePath -Path $workflow.FullName)"
        Assert-Condition ($composeMatches.Count -eq 1) "Deploy workflow must reference exactly one compose file: $(Get-RelativePath -Path $workflow.FullName)"

        $workflowId = [System.IO.Path]::GetFileNameWithoutExtension($workflow.Name)
        $workflowId = ($workflowId -replace '^deploy-', '' -replace '[^a-zA-Z0-9-]', '-').ToLower()

        $entries += [pscustomobject]@{
            Id = $workflowId
            WorkflowPath = Get-RelativePath -Path $workflow.FullName
            ComposePath = $composeMatches[0]
        }
    }

    return $entries
}

Assert-FileExists -Path $CatalogPath -Label "Catalog"
Assert-FileExists -Path $SchemaPath -Label "Schema"
Assert-FileExists -Path $WorkflowDir -Label "Workflow directory"

$catalog = Get-Content -LiteralPath $CatalogPath -Raw | ConvertFrom-Json -Depth 20
$schema = Get-Content -LiteralPath $SchemaPath -Raw | ConvertFrom-Json -Depth 20
$workflowEntries = Get-DeployWorkflowEntries -Path $WorkflowDir

Assert-Condition ($schema.'$id' -ne $null) "Schema must include `$id."
Assert-Condition ($schema.'$defs'.service -ne $null) "Schema must include `$defs.service definition."
Assert-Condition ($catalog.schemaVersion -match '^1\.[0-9]+$') "Catalog schemaVersion must match 1.x format."
Assert-Condition ($catalog.services.Count -eq $workflowEntries.Count) "Catalog must include exactly one entry for each deploy workflow. Catalog=$($catalog.services.Count) Workflows=$($workflowEntries.Count)."

$serviceIds = @{}
$workflowPaths = @{}
$composePaths = @{}
foreach ($service in $catalog.services) {
    Assert-Condition ($service.id -match '^[a-z0-9-]+$') "Invalid service id: $($service.id)"
    Assert-Condition (-not $serviceIds.ContainsKey($service.id)) "Duplicate service id: $($service.id)"
    $serviceIds[$service.id] = $true

    Assert-Condition (-not $workflowPaths.ContainsKey($service.workflowPath)) "Duplicate workflowPath: $($service.workflowPath)"
    $workflowPaths[$service.workflowPath] = $service.id

    Assert-Condition (-not $composePaths.ContainsKey($service.composePath)) "Duplicate composePath: $($service.composePath)"
    $composePaths[$service.composePath] = $service.id

    Assert-Condition (Test-Path -LiteralPath $service.composePath) "composePath missing for $($service.id): $($service.composePath)"
    Assert-Condition (Test-Path -LiteralPath $service.workflowPath) "workflowPath missing for $($service.id): $($service.workflowPath)"
    Assert-Condition ($service.changeWindow -is [string] -and -not [string]::IsNullOrWhiteSpace($service.changeWindow)) "changeWindow required for $($service.id)"
    Assert-Condition ($service.notes -is [string] -and -not [string]::IsNullOrWhiteSpace($service.notes)) "notes required for $($service.id)"

    $expectedHost = if ($service.tier -eq 'critical') { 'hac-critical' } else { 'hac-noncritical' }
    Assert-Condition ($service.host -eq $expectedHost) "Host/tier mismatch for $($service.id): tier=$($service.tier) host=$($service.host)"

    $expectedTier = if ($service.composePath.StartsWith('Docker-Critical/')) { 'critical' } else { 'noncritical' }
    Assert-Condition ($service.tier -eq $expectedTier) "composePath/tier mismatch for $($service.id): $($service.composePath)"

    $expectedId = [System.IO.Path]::GetFileNameWithoutExtension($service.workflowPath)
    $expectedId = ($expectedId -replace '^deploy-', '' -replace '[^a-zA-Z0-9-]', '-').ToLower()
    Assert-Condition ($service.id -eq $expectedId) "Service id/workflow mismatch for $($service.id): expected $expectedId from $($service.workflowPath)"

    foreach ($dep in $service.dependencies) {
        Assert-Condition ($dep -ne $service.id) "Service $($service.id) cannot depend on itself."
    }
}

$workflowByPath = @{}
$workflowById = @{}
foreach ($entry in $workflowEntries) {
    Assert-Condition (-not $workflowByPath.ContainsKey($entry.WorkflowPath)) "Duplicate deploy workflow discovered: $($entry.WorkflowPath)"
    Assert-Condition (-not $workflowById.ContainsKey($entry.Id)) "Duplicate deploy workflow id discovered: $($entry.Id)"
    $workflowByPath[$entry.WorkflowPath] = $entry
    $workflowById[$entry.Id] = $entry
}

foreach ($service in $catalog.services) {
    foreach ($dep in $service.dependencies) {
        Assert-Condition ($serviceIds.ContainsKey($dep)) "Unknown dependency '$dep' in service '$($service.id)'."
    }

    Assert-Condition ($workflowByPath.ContainsKey($service.workflowPath)) "Catalog references unknown workflowPath for $($service.id): $($service.workflowPath)"
    $workflowEntry = $workflowByPath[$service.workflowPath]
    Assert-Condition ($workflowEntry.ComposePath -eq $service.composePath) "Catalog composePath mismatch for $($service.id): expected $($workflowEntry.ComposePath)"
}

foreach ($workflowEntry in $workflowEntries) {
    Assert-Condition ($serviceIds.ContainsKey($workflowEntry.Id)) "Missing catalog entry for deploy workflow id '$($workflowEntry.Id)' ($($workflowEntry.WorkflowPath))."
}

Write-Host "Service catalog validation passed for $($catalog.services.Count) services across $($workflowEntries.Count) deploy workflows."
