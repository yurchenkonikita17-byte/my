# Claude Code status line for Windows: shows how much of the context window is left, in percent.
# Same output as statusline.py, without needing Python. Works in Windows PowerShell 5.1 and PowerShell 7.
# Kept ASCII-only so Windows PowerShell 5.1 reads it correctly without a BOM.

$BarWidth = 10
$DefaultWindow = 200000

[Console]::InputEncoding = [Text.Encoding]::UTF8
[Console]::OutputEncoding = [Text.Encoding]::UTF8

function Get-UsedTokens($usage) {
    if ($null -eq $usage) { return $null }
    $sum = 0
    foreach ($k in 'input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens') {
        if ($usage.$k) { $sum += [double]$usage.$k }
    }
    return $sum
}

# Usage of the latest assistant message in the transcript (older Claude Code).
function Get-TranscriptUsage($path) {
    if (-not $path -or -not (Test-Path -LiteralPath $path)) { return $null }
    $lines = @(Get-Content -LiteralPath $path -Encoding UTF8)
    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        try { $entry = $lines[$i] | ConvertFrom-Json } catch { continue }
        if ($entry.message -and $entry.message.usage -and -not $entry.isSidechain) {
            return $entry.message.usage
        }
    }
    return $null
}

function Get-RemainingPercent($data) {
    $ctx = $data.context_window
    if ($ctx) {
        # Newer Claude Code versions report the percentage directly.
        if ($null -ne $ctx.remaining_percentage) { return [double]$ctx.remaining_percentage }
        if ($null -ne $ctx.used_percentage) { return 100 - [double]$ctx.used_percentage }
    }
    $size = $DefaultWindow
    if ($ctx -and $ctx.context_window_size) { $size = [double]$ctx.context_window_size }
    $used = $null
    if ($ctx) { $used = Get-UsedTokens $ctx.current_usage }
    if ($null -eq $used) { $used = Get-UsedTokens (Get-TranscriptUsage $data.transcript_path) }
    if ($null -eq $used) { return 100 }  # nothing sent yet
    return 100 * (1 - $used / $size)
}

$data = $null
try { $data = [Console]::In.ReadToEnd() | ConvertFrom-Json } catch { }
if ($null -eq $data) { $data = New-Object PSObject }

$pct = [Math]::Max(0, [Math]::Min(100, (Get-RemainingPercent $data)))
$esc = [char]27
if ($pct -gt 50) { $color = "$esc[32m" } elseif ($pct -gt 20) { $color = "$esc[33m" } else { $color = "$esc[31m" }
$reset = "$esc[0m"
$filled = [int][Math]::Round($pct / 100 * $BarWidth, [MidpointRounding]::AwayFromZero)
$bar = ([string][char]0x2588) * $filled + ([string][char]0x2591) * ($BarWidth - $filled)

$prefix = ''
if ($data.model -and $data.model.display_name) { $prefix = "$esc[2m$($data.model.display_name) $([char]0x00B7) $reset" }
[Console]::Out.Write("$prefix$color$bar $([Math]::Round($pct))%$reset tokens left`n")
