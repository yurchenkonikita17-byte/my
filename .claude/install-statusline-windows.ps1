# Installs the remaining-tokens status line for Claude Code on Windows, for all projects.
# Run in PowerShell:
#   irm https://raw.githubusercontent.com/yurchenkonikita17-byte/my/main/.claude/install-statusline-windows.ps1 | iex

$dir = Join-Path $env:USERPROFILE '.claude'
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$script = Join-Path $dir 'statusline.ps1'
Invoke-WebRequest -UseBasicParsing -OutFile $script `
    -Uri 'https://raw.githubusercontent.com/yurchenkonikita17-byte/my/main/.claude/statusline.ps1'

# Add statusLine to ~/.claude/settings.json, keeping every other setting.
$settingsPath = Join-Path $dir 'settings.json'
$settings = $null
if (Test-Path -LiteralPath $settingsPath) {
    $raw = [IO.File]::ReadAllText($settingsPath)
    if ($raw.Trim()) { $settings = $raw | ConvertFrom-Json }
}
if ($null -eq $settings) { $settings = New-Object PSObject }

$command = 'powershell -NoProfile -ExecutionPolicy Bypass -File "' + ($script -replace '\\', '/') + '"'
$statusLine = [pscustomobject]@{ type = 'command'; command = $command; padding = 0 }
$settings | Add-Member -Force -MemberType NoteProperty -Name statusLine -Value $statusLine

# Write UTF-8 without BOM so Claude Code can parse it.
[IO.File]::WriteAllText($settingsPath, ($settings | ConvertTo-Json -Depth 32), (New-Object Text.UTF8Encoding $false))

Write-Host "Status line installed. Restart Claude Code to see it."
