# Apply a reviewed Poseidon 3090 OC profile (default: Kyle's 3090 profile).
# Dry-run by default; pass -Execute to actually run nvidia-smi (needs an
# elevated PowerShell). The core offset is a manual Afterburner/NVIDIA App
# step - the tool prints it and never pretends it was set.
#   .\scripts\oc-apply.ps1 [-Profile kyle-3090-mem405] [-Device 0] [-Execute]
param(
    [string]$Profile = "kyle-3090-efficiency",
    [int]$Device = 0,
    [switch]$Execute
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$argsList = @("scripts/poseidon_oc.py", "apply", "--profile", $Profile, "--device", $Device)
if ($Execute) { $argsList += "--execute" }
& python @argsList
exit $LASTEXITCODE
