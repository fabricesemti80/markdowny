$ErrorActionPreference = 'Stop'

Write-Host "Uninstalling docflux (dfx)..."

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv not found – nothing to uninstall."
    exit 0
}

$toolList = uv tool list 2>$null
if ($toolList -match "md-converter") {
    uv tool uninstall md-converter
    Write-Host "Removed dfx tool."
} else {
    Write-Host "dfx is not currently installed via uv."
}

Write-Host ""
Write-Host "Done! The following were NOT removed (they may be used by other tools):"
Write-Host "  - uv"
Write-Host "  - pandoc"
Write-Host "To remove those manually:"
Write-Host "  winget uninstall pandoc"
Write-Host "  Remove-Item -Recurse -Force `"$env:USERPROFILE\.local\bin\uv`""
