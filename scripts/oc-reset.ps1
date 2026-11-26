# Release the Poseidon 3090 clock locks and persistence mode.
# Dry-run by default; pass -Execute to actually run nvidia-smi (needs an
# elevated PowerShell).
#   .\scripts\oc-reset.ps1 [-Device 0] [-Execute]
param(
    [int]$Device = 0,
    [switch]$Execute
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$argsList = @("scripts/poseidon_oc.py", "reset", "--device", $Device)
if ($Execute) { $argsList += "--execute" }
& python @argsList
exit $LASTEXITCODE
