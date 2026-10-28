# Run explicitly as administrator. Changes only this app's executables, never user data.
param([switch]$Restart)
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run PowerShell as administrator, then run this script again.'
}
$root = $PSScriptRoot
$candidates = @(
    (Join-Path $root 'Reset.exe'),
    (Join-Path $root 'ResetTerminal.exe'),
    (Join-Path $root 'vendor\psmux\psmux.exe'),
    (Join-Path $root '_internal\vendor\psmux\psmux.exe')
)
foreach ($target in $candidates) {
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { continue }
    if ([IO.Path]::GetFileName($target) -eq 'psmux.exe' -and (Get-AuthenticodeSignature -LiteralPath $target).Status -ne 'Valid') {
        throw 'Psmux signature is not valid. Do not change its security label.'
    }
    # High label preserves an elevated parent's integrity; it does not grant a normal user elevation.
    & icacls.exe $target /setintegritylevel H
    if ($LASTEXITCODE -ne 0) { throw 'Could not repair this app executable.' }
}
Write-Output 'Done. Reopen Reset. No profile permissions or Codex sandbox settings were changed.'
if ($Restart) {
    $entry = Join-Path $PSScriptRoot 'Reset.exe'
    if (Test-Path -LiteralPath $entry -PathType Leaf) { Start-Process -FilePath $entry -WorkingDirectory $PSScriptRoot -WindowStyle Normal }
}
