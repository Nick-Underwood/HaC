param(
    [string]$TemplatePath = ".github/agents/hac-general.agent.md",
    [string]$OutputPath = ".github/agents/hac-general.agent.md"
)

$ErrorActionPreference = "Stop"

function Assert-FileExists {
    param([string]$Path, [string]$Label)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label not found: $Path"
    }
}

Assert-FileExists -Path $TemplatePath -Label "Source"

if (Test-Path -LiteralPath $OutputPath) {
    Write-Host "Agent already exists at $OutputPath"
    exit 0
}

$template = Get-Content -LiteralPath $TemplatePath -Raw
$template = $template -replace '(?m)^name:\s*.*$', 'name: hac-general'
$template | Set-Content -LiteralPath $OutputPath

    Write-Host "Copied Copilot agent from $TemplatePath to $OutputPath"