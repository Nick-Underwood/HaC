param(
    [string]$CatalogPath = "development/service-catalog/data/services.catalog.json",
    [string]$InventoryPath = "development/service-catalog/data/services.inventory.json"
)

$ErrorActionPreference = "Stop"

function Assert-FileExists {
    param([string]$Path, [string]$Label)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label not found: $Path"
    }
}

Assert-FileExists -Path $CatalogPath -Label "Catalog"
Assert-FileExists -Path $InventoryPath -Label "Inventory"

$catalog = Get-Content -LiteralPath $CatalogPath -Raw | ConvertFrom-Json -Depth 20
$inventory = Get-Content -LiteralPath $InventoryPath -Raw | ConvertFrom-Json -Depth 20

$catalogById = @{}
foreach ($service in $catalog.services) {
    $catalogById[$service.id] = $service
}

$mergedServices = foreach ($inventoryService in ($inventory.services | Sort-Object id)) {
    if ($catalogById.ContainsKey($inventoryService.id)) {
        $existing = $catalogById[$inventoryService.id]
        [pscustomobject][ordered]@{
            id = $existing.id
            name = $existing.name
            tier = $inventoryService.tier
            host = $inventoryService.host
            domain = $existing.domain
            composePath = $inventoryService.composePath
            workflowPath = $inventoryService.workflowPath
            owner = $existing.owner
            criticality = $existing.criticality
            rollbackClass = $existing.rollbackClass
            dependencies = @($existing.dependencies)
            changeWindow = if ($existing.changeWindow) { $existing.changeWindow } else { $inventoryService.changeWindow }
            notes = if ($existing.notes) { $existing.notes } else { $inventoryService.notes }
        }
    }
    else {
        [pscustomobject][ordered]@{
            id = $inventoryService.id
            name = $inventoryService.name
            tier = $inventoryService.tier
            host = $inventoryService.host
            domain = $inventoryService.domain
            composePath = $inventoryService.composePath
            workflowPath = $inventoryService.workflowPath
            owner = $inventoryService.owner
            criticality = $inventoryService.criticality
            rollbackClass = $inventoryService.rollbackClass
            dependencies = @($inventoryService.dependencies)
            changeWindow = $inventoryService.changeWindow
            notes = $inventoryService.notes
        }
    }
}

$mergedDocument = [ordered]@{
    schemaVersion = $catalog.schemaVersion
    generatedAt = (Get-Date).ToUniversalTime().ToString('o')
    services = @($mergedServices)
}

$mergedDocument | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $CatalogPath

Write-Host "Synced catalog at $CatalogPath with $($mergedServices.Count) services from inventory."