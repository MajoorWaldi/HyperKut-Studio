# Starts the comfy-api-proxy (the Comfy SDK talks to it) and the studio. ComfyUI must already be running.
param([string]$ComfyUI = 'http://127.0.0.1:8188', [int]$Port = 8090, [int]$ProxyPort = 8189, [string]$OutputDir = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:SECATOR_COMFYUI_URL = $ComfyUI
$env:COMFY_BASE_URL = "http://127.0.0.1:$ProxyPort"
if ($OutputDir) { $env:SECATOR_OUTPUT_DIR = (Resolve-Path -LiteralPath $OutputDir).Path }
Push-Location -LiteralPath $root
try {
    & "$root\.venv\Scripts\comfy-api-proxy.exe" start --comfyui $ComfyUI --port $ProxyPort
    if ($LASTEXITCODE -ne 0) { throw 'The Comfy API proxy could not start. Check comfy-api-proxy status.' }
    & "$root\.venv\Scripts\python.exe" -m uvicorn backend.server:create_app --factory --host 127.0.0.1 --port $Port
} finally {
    Pop-Location
}
