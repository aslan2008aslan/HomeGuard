<#
.SYNOPSIS
  清理 turbopi-AGH2 工作区里的临时/生成文件，保留源码与文档。

.DESCRIPTION
  用途：开发与调试过程中会不断产生临时文件（__pycache__、.pyc、日志、抓图、
  临时 .sh 探测脚本等）。本脚本把它们清掉，同时**绝不碰**源码、文档和正式工具脚本。

  与 "clean_restart.sh" 的区别（名字像，用途不同，别混）：
    - clean_restart.sh   ：在树莓派上跑，清理**容器内的设备进程**后重启设备程序
    - clean_workspace.ps1：在本机跑，清理**工作区里的临时文件**（本脚本）

.PARAMETER WhatIf
  只列将删除的内容，不实际删除。**建议先跑这个。**

.PARAMETER IncludeLogs
  一并删除日志类文件（*.log、hub_stderr.log 等）。默认不删，因为排查时可能还要看。

.EXAMPLE
  powershell -File clean_workspace.ps1 -WhatIf     # 预览
  powershell -File clean_workspace.ps1             # 执行（保留日志）
  powershell -File clean_workspace.ps1 -IncludeLogs # 连日志一起删
#>
param(
  [switch]$WhatIf,
  [switch]$IncludeLogs
)

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Root   # tools/ 的上一级 = 仓库根

# ---------------------------------------------------------------------------
# 保留清单：这些**永不删除**。写死路径，防止误删。
# ---------------------------------------------------------------------------
$Keep = @(
  'README.md',
  '.gitignore',
  '项目介绍.md',
  '方案规划.md',
  '免密登录配置.md',
  '2026年江苏省AI+科学与工程创新实践黑客松_【高校组】 参赛指南.md',
  'docs\小车接入实测记录.md',
  'docs\恢复后待办与验证清单.md',
  'tools\bat.sh',
  'tools\clean_restart.sh',
  'tools\start_device.sh',
  'tools\fix_battery_topic.ps1',
  'tools\patch_battery.py'
) | ForEach-Object { Join-Path $Root $_ }

# ---------------------------------------------------------------------------
# 待删模式：目录名与文件通配
# ---------------------------------------------------------------------------
$DirPatterns = @('__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache')
$FilePatterns = @('*.pyc', '*.pyo', '*.tmp', 'temp_*', '*.bak', '*.orig')
if ($IncludeLogs) { $FilePatterns += @('*.log', '*.jsonl') }

function Say([string]$m) { Write-Host $m }

Say "=== clean_workspace.ps1 ==="
Say "仓库根: $Root"
if ($WhatIf)    { Say "模式: 预览（不会删除任何东西）" }
if (-not $WhatIf) { Say "模式: 执行" }
Say "日志: $(if ($IncludeLogs) { '一并删除' } else { '保留（加 -IncludeLogs 才删）' })"
Say ""

$targets = New-Object System.Collections.Generic.List[object]

# 目录
foreach ($p in $DirPatterns) {
  Get-ChildItem -Path $Root -Recurse -Directory -Filter $p -Force -ErrorAction SilentlyContinue |
    ForEach-Object { $targets.Add([pscustomobject]@{ Kind = 'dir'; Item = $_ }) }
}
# 文件
foreach ($p in $FilePatterns) {
  Get-ChildItem -Path $Root -Recurse -File -Filter $p -Force -ErrorAction SilentlyContinue |
    ForEach-Object { $targets.Add([pscustomobject]@{ Kind = 'file'; Item = $_ }) }
}

# 安全闸：任何落在保留清单里的，剔除并告警
$safe = New-Object System.Collections.Generic.List[object]
foreach ($t in $targets) {
  $full = $t.Item.FullName
  if ($Keep -contains $full) {
    Say "  [跳过] 命中保留清单: $full"
    continue
  }
  $safe.Add($t)
}

if ($safe.Count -eq 0) {
  Say "没有需要清理的内容。工作区已是干净的。"
  Say ""
  Say "--- 当前内容 ---"
  Get-ChildItem $Root -Recurse -File -Force |
    Where-Object { $_.FullName -notmatch '\\\.git\\' } |
    ForEach-Object { Say ("  " + $_.FullName.Replace($Root + '\', '') + "  ($($_.Length) B)") }
  exit 0
}

# 去掉位于待删目录内部的子项：父目录一删，子项就“不存在”了，
# 否则会报一堆假的“删除失败”。
$dirs = $safe | Where-Object { $_.Kind -eq 'dir' } | ForEach-Object { $_.Item.FullName }
$final = $safe | Where-Object {
  if ($_.Kind -ne 'file') { return $true }
  $p = $_.Item.FullName
  foreach ($d in $dirs) {
    if ($p.StartsWith($d + '\', [System.StringComparison]::OrdinalIgnoreCase)) { return $false }
  }
  return $true
}

Say "--- 将删除 $($final.Count) 项 ---"
foreach ($t in $final) {
  $rel = $t.Item.FullName.Replace($Root + '\', '')
  Say ("  [$($t.Kind)] $rel")
}

if ($WhatIf) {
  Say ""
  Say "预览结束。确认无误后去掉 -WhatIf 再跑一次。"
  exit 0
}

Say ""
Say '--- 删除中 ---'
$failed = 0
foreach ($t in $final) {
  $rel = $t.Item.FullName.Replace($Root + '\', '')
  try {
    if ($t.Kind -eq 'dir') {
      Remove-Item -LiteralPath $t.Item.FullName -Recurse -Force -ErrorAction Stop
    } else {
      Remove-Item -LiteralPath $t.Item.FullName -Force -ErrorAction Stop
    }
    Say "  已删除 $rel"
  } catch {
    Say "  !! 删除失败 $rel : $($_.Exception.Message)"
    $failed++
  }
}

Say ""
if ($failed -gt 0) {
  Say "完成，但有 $failed 项删除失败（可能被占用，关掉相关程序后重跑）。"
} else {
  Say '完成，全部删除成功。'
}

Say ""
Say '--- 清理后的工作区 ---'
Get-ChildItem $Root -Recurse -File -Force |
  Where-Object { $_.FullName -notmatch '\\\.git\\' } |
  ForEach-Object { Say ("  " + $_.FullName.Replace($Root + '\', '') + "  ($($_.Length) B)") }
