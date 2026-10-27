param(
    [Parameter(Mandatory = $true)]
    [string]$MsGraphToken,

    [Parameter(Mandatory = $true)]
    [string]$VikunjaToken,

    [Parameter(Mandatory = $true)]
    [string]$VikunjaUrl,

    [Parameter(Mandatory = $true)]
    [string]$ConfigPath,

    [string]$OutputDir = "development/task-automation/reports",
    [switch]$IncludeCompleted
)

$ErrorActionPreference = "Stop"

function Invoke-JsonApi {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][hashtable]$Headers,
        $Body = $null
    )

    if ($null -ne $Body) {
        return Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 20)
    }

    return Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers
}

function Normalize-Text {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return "" }
    $n = $Text.Trim().ToLowerInvariant()
    $n = [regex]::Replace($n, "\s+", " ")
    return $n
}

function Get-MsTodoLists {
    param([hashtable]$Headers)
    $url = "https://graph.microsoft.com/v1.0/me/todo/lists"
    $all = @()

    while ($url) {
        $resp = Invoke-JsonApi -Method GET -Url $url -Headers $Headers
        if ($resp.value) { $all += $resp.value }
        $url = $resp.'@odata.nextLink'
    }

    return $all
}

function Get-MsTodoTasksWithChecklist {
    param(
        [hashtable]$Headers,
        [string]$ListId,
        [bool]$IncludeDone
    )

    $url = "https://graph.microsoft.com/v1.0/me/todo/lists/$ListId/tasks?`$top=200"
    $tasks = @()

    while ($url) {
        $resp = Invoke-JsonApi -Method GET -Url $url -Headers $Headers
        if ($resp.value) { $tasks += $resp.value }
        $url = $resp.'@odata.nextLink'
    }

    $out = @()
    foreach ($t in $tasks) {
        $isDone = ($t.status -eq "completed")
        if (-not $IncludeDone -and $isDone) { continue }

        $checkUrl = "https://graph.microsoft.com/v1.0/me/todo/lists/$ListId/tasks/$($t.id)/checklistItems"
        $checkItems = @()
        $nextChecklistUrl = $checkUrl
        while ($nextChecklistUrl) {
            $cResp = Invoke-JsonApi -Method GET -Url $nextChecklistUrl -Headers $Headers
            if ($cResp.value) { $checkItems += $cResp.value }
            $nextChecklistUrl = $cResp.'@odata.nextLink'
        }

        $out += [pscustomobject]@{
            Id = $t.id
            Title = $t.title
            Status = $t.status
            IsDone = $isDone
            DueAt = if ($t.dueDateTime) { $t.dueDateTime.dateTime } else { $null }
            ChecklistItems = @($checkItems | ForEach-Object {
                [pscustomobject]@{
                    Id = $_.id
                    Title = $_.displayName
                    IsDone = ($_.isChecked -eq $true)
                }
            })
        }
    }

    return $out
}

function Get-VikunjaProjects {
    param(
        [string]$BaseUrl,
        [hashtable]$Headers
    )

    $url = "$BaseUrl/api/v1/projects"
    $resp = Invoke-JsonApi -Method GET -Url $url -Headers $Headers
    return @($resp)
}

function Get-VikunjaTasksAll {
    param(
        [string]$BaseUrl,
        [hashtable]$Headers,
        [bool]$IncludeDone
    )

    $filter = if ($IncludeDone) { "" } else { "&filter=done%3Dfalse" }
    $url = "$BaseUrl/api/v1/tasks/all?sort_by=updated&order_by=desc&per_page=2000$filter"
    $resp = Invoke-JsonApi -Method GET -Url $url -Headers $Headers
    return @($resp)
}

function Get-VikunjaParentId {
    param($Task)

    $candidates = @(
        $Task.parent_task_id,
        $Task.parentTaskId,
        $Task.parenttaskid,
        $Task.parent_id,
        $Task.parent
    )

    foreach ($c in $candidates) {
        if ($null -ne $c -and "$c" -ne "" -and "$c" -ne "0") {
            return [string]$c
        }
    }

    return $null
}

function Compare-SubItems {
    param(
        [array]$MsSubItems,
        [array]$VikunjaChildren
    )

    $msByNorm = @{}
    foreach ($i in $MsSubItems) {
        $k = Normalize-Text -Text $i.Title
        if (-not $msByNorm.ContainsKey($k)) { $msByNorm[$k] = @() }
        $msByNorm[$k] += $i
    }

    $vkByNorm = @{}
    foreach ($i in $VikunjaChildren) {
        $k = Normalize-Text -Text $i.title
        if (-not $vkByNorm.ContainsKey($k)) { $vkByNorm[$k] = @() }
        $vkByNorm[$k] += $i
    }

    $allKeys = @($msByNorm.Keys + $vkByNorm.Keys | Sort-Object -Unique)
    $diffs = @()

    foreach ($k in $allKeys) {
        $msItems = if ($msByNorm.ContainsKey($k)) { $msByNorm[$k] } else { @() }
        $vkItems = if ($vkByNorm.ContainsKey($k)) { $vkByNorm[$k] } else { @() }

        if ($msItems.Count -eq 0) {
            foreach ($v in $vkItems) {
                $diffs += [pscustomobject]@{
                    Type = "SubItemOnlyInVikunja"
                    Key = $k
                    MsTitle = ""
                    VkTitle = $v.title
                    MsDone = ""
                    VkDone = [bool]$v.done
                }
            }
            continue
        }

        if ($vkItems.Count -eq 0) {
            foreach ($m in $msItems) {
                $diffs += [pscustomobject]@{
                    Type = "SubItemOnlyInMsTodo"
                    Key = $k
                    MsTitle = $m.Title
                    VkTitle = ""
                    MsDone = [bool]$m.IsDone
                    VkDone = ""
                }
            }
            continue
        }

        $pairs = [Math]::Min($msItems.Count, $vkItems.Count)
        for ($idx = 0; $idx -lt $pairs; $idx++) {
            $m = $msItems[$idx]
            $v = $vkItems[$idx]
            if ([bool]$m.IsDone -ne [bool]$v.done) {
                $diffs += [pscustomobject]@{
                    Type = "SubItemStatusMismatch"
                    Key = $k
                    MsTitle = $m.Title
                    VkTitle = $v.title
                    MsDone = [bool]$m.IsDone
                    VkDone = [bool]$v.done
                }
            }
        }

        if ($msItems.Count -gt $vkItems.Count) {
            for ($i = $pairs; $i -lt $msItems.Count; $i++) {
                $m = $msItems[$i]
                $diffs += [pscustomobject]@{
                    Type = "SubItemOnlyInMsTodo"
                    Key = $k
                    MsTitle = $m.Title
                    VkTitle = ""
                    MsDone = [bool]$m.IsDone
                    VkDone = ""
                }
            }
        }

        if ($vkItems.Count -gt $msItems.Count) {
            for ($i = $pairs; $i -lt $vkItems.Count; $i++) {
                $v = $vkItems[$i]
                $diffs += [pscustomobject]@{
                    Type = "SubItemOnlyInVikunja"
                    Key = $k
                    MsTitle = ""
                    VkTitle = $v.title
                    MsDone = ""
                    VkDone = [bool]$v.done
                }
            }
        }
    }

    return $diffs
}

if (-not (Test-Path $ConfigPath)) {
    throw "Config file not found: $ConfigPath"
}

$config = Get-Content -Raw -Path $ConfigPath | ConvertFrom-Json
if (-not $config.mappings -or $config.mappings.Count -eq 0) {
    throw "Config must include at least one mapping in 'mappings'."
}

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

$runAt = Get-Date
$stamp = $runAt.ToString("yyyyMMdd-HHmmss")
$reportPath = Join-Path $OutputDir "ms-vikunja-diff-$stamp.md"
$jsonPath = Join-Path $OutputDir "ms-vikunja-diff-$stamp.json"

$msHeaders = @{ Authorization = "Bearer $MsGraphToken" }
$vkBase = $VikunjaUrl.TrimEnd('/')
$vkHeaders = @{ Authorization = "Bearer $VikunjaToken" }

Write-Host "Loading Microsoft To Do lists..."
$msLists = Get-MsTodoLists -Headers $msHeaders
$msListByName = @{}
foreach ($l in $msLists) { $msListByName[$l.displayName] = $l }

Write-Host "Loading Vikunja projects..."
$vkProjects = Get-VikunjaProjects -BaseUrl $vkBase -Headers $vkHeaders
$vkProjectByName = @{}
foreach ($p in $vkProjects) { $vkProjectByName[$p.title] = $p }

Write-Host "Loading Vikunja tasks..."
$vkTasksAll = Get-VikunjaTasksAll -BaseUrl $vkBase -Headers $vkHeaders -IncludeDone:$IncludeCompleted.IsPresent

$report = @()
$report += "# Microsoft To Do vs Vikunja Diff"
$report += ""
$report += "- Generated: $($runAt.ToString('u'))"
$report += "- Include completed: $($IncludeCompleted.IsPresent)"
$report += ""

$allResults = @()

foreach ($m in $config.mappings) {
    $msListName = [string]$m.msTodoListName
    $vkProjectName = [string]$m.vikunjaProjectName

    $report += "## Mapping: $msListName -> $vkProjectName"

    if (-not $msListByName.ContainsKey($msListName)) {
        $msg = "MS To Do list not found: $msListName"
        $report += "- ERROR: $msg"
        $report += ""
        $allResults += [pscustomobject]@{ Mapping = "$msListName -> $vkProjectName"; Error = $msg }
        continue
    }

    if (-not $vkProjectByName.ContainsKey($vkProjectName)) {
        $msg = "Vikunja project not found: $vkProjectName"
        $report += "- ERROR: $msg"
        $report += ""
        $allResults += [pscustomobject]@{ Mapping = "$msListName -> $vkProjectName"; Error = $msg }
        continue
    }

    $msListId = [string]$msListByName[$msListName].id
    $vkProjectId = [int]$vkProjectByName[$vkProjectName].id

    Write-Host "Comparing '$msListName' with '$vkProjectName'..."

    $msTasks = Get-MsTodoTasksWithChecklist -Headers $msHeaders -ListId $msListId -IncludeDone:$IncludeCompleted.IsPresent
    $vkTasks = @($vkTasksAll | Where-Object { [int]$_.project_id -eq $vkProjectId })

    $vkChildrenByParent = @{}
    foreach ($t in $vkTasks) {
        $pid = Get-VikunjaParentId -Task $t
        if ($pid) {
            if (-not $vkChildrenByParent.ContainsKey($pid)) { $vkChildrenByParent[$pid] = @() }
            $vkChildrenByParent[$pid] += $t
        }
    }

    $vkRootTasks = @($vkTasks | Where-Object { -not (Get-VikunjaParentId -Task $_) })

    $vkByNorm = @{}
    foreach ($t in $vkRootTasks) {
        $k = Normalize-Text -Text $t.title
        if (-not $vkByNorm.ContainsKey($k)) { $vkByNorm[$k] = @() }
        $vkByNorm[$k] += $t
    }

    $paired = @()
    $onlyMs = @()
    $onlyVk = @()
    $mismatches = @()

    foreach ($ms in $msTasks) {
        $k = Normalize-Text -Text $ms.Title
        if ($vkByNorm.ContainsKey($k) -and $vkByNorm[$k].Count -gt 0) {
            $vk = $vkByNorm[$k][0]
            if ($vkByNorm[$k].Count -gt 1) {
                $vkByNorm[$k] = @($vkByNorm[$k] | Select-Object -Skip 1)
            }
            else {
                $vkByNorm.Remove($k)
            }

            $paired += [pscustomobject]@{ Ms = $ms; Vk = $vk }
        }
        else {
            $onlyMs += $ms
        }
    }

    foreach ($remainingKey in $vkByNorm.Keys) {
        foreach ($vk in $vkByNorm[$remainingKey]) {
            $onlyVk += $vk
        }
    }

    foreach ($pair in $paired) {
        $ms = $pair.Ms
        $vk = $pair.Vk

        $msDone = [bool]$ms.IsDone
        $vkDone = [bool]$vk.done
        $msDue = if ($ms.DueAt) { ([datetime]$ms.DueAt).ToString("yyyy-MM-dd") } else { "" }
        $vkDue = if ($vk.due_date) { ([datetime]$vk.due_date).ToString("yyyy-MM-dd") } else { "" }

        if ($msDone -ne $vkDone) {
            $mismatches += [pscustomobject]@{
                Type = "TaskStatusMismatch"
                Title = $ms.Title
                MsDone = $msDone
                VkDone = $vkDone
                MsDue = $msDue
                VkDue = $vkDue
            }
        }

        if ($msDue -ne $vkDue) {
            $mismatches += [pscustomobject]@{
                Type = "TaskDueDateMismatch"
                Title = $ms.Title
                MsDone = $msDone
                VkDone = $vkDone
                MsDue = $msDue
                VkDue = $vkDue
            }
        }

        $vkChildren = if ($vkChildrenByParent.ContainsKey([string]$vk.id)) { $vkChildrenByParent[[string]$vk.id] } else { @() }
        $subDiffs = Compare-SubItems -MsSubItems $ms.ChecklistItems -VikunjaChildren $vkChildren
        foreach ($sd in $subDiffs) {
            $mismatches += [pscustomobject]@{
                Type = $sd.Type
                Title = $ms.Title
                MsDone = $sd.MsDone
                VkDone = $sd.VkDone
                MsDue = ""
                VkDue = ""
                MsSubTitle = $sd.MsTitle
                VkSubTitle = $sd.VkTitle
            }
        }
    }

    $report += "- MS tasks: $($msTasks.Count)"
    $report += "- Vikunja root tasks: $($vkRootTasks.Count)"
    $report += "- Matched root tasks: $($paired.Count)"
    $report += "- Only in MS To Do: $($onlyMs.Count)"
    $report += "- Only in Vikunja: $($onlyVk.Count)"
    $report += "- Mismatches (including sub-items): $($mismatches.Count)"
    $report += ""

    if ($onlyMs.Count -gt 0) {
        $report += "### Only In MS To Do"
        foreach ($x in $onlyMs) {
            $report += "- $($x.Title)"
        }
        $report += ""
    }

    if ($onlyVk.Count -gt 0) {
        $report += "### Only In Vikunja"
        foreach ($x in $onlyVk) {
            $report += "- $($x.title)"
        }
        $report += ""
    }

    if ($mismatches.Count -gt 0) {
        $report += "### Mismatches"
        foreach ($d in $mismatches) {
            if ($d.Type -like "SubItem*") {
                $report += "- [$($d.Type)] Task '$($d.Title)' | MS sub: '$($d.MsSubTitle)' (done=$($d.MsDone)) | Vikunja sub: '$($d.VkSubTitle)' (done=$($d.VkDone))"
            }
            else {
                $report += "- [$($d.Type)] '$($d.Title)' | MS done=$($d.MsDone), Vikunja done=$($d.VkDone), MS due='$($d.MsDue)', Vikunja due='$($d.VkDue)'"
            }
        }
        $report += ""
    }

    $allResults += [pscustomobject]@{
        Mapping = "$msListName -> $vkProjectName"
        MsTasks = $msTasks.Count
        VikunjaRootTasks = $vkRootTasks.Count
        Matched = $paired.Count
        OnlyMs = $onlyMs.Count
        OnlyVikunja = $onlyVk.Count
        Mismatches = $mismatches
    }
}

$report | Set-Content -Path $reportPath -Encoding UTF8
$allResults | ConvertTo-Json -Depth 20 | Set-Content -Path $jsonPath -Encoding UTF8

Write-Host "Diff complete."
Write-Host "Markdown report: $reportPath"
Write-Host "JSON report: $jsonPath"
