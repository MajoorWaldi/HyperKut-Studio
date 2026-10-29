# Starts the comfy-api-proxy (the Comfy SDK talks to it) and the studio. ComfyUI must already be running.
param([string]$ComfyUI = 'http://127.0.0.1:8188', [int]$Port = 8090, [int]$ProxyPort = 0, [string]$OutputDir = '', [string]$Workspace = '', [ValidateSet('shared_local','remote_artifacts')][string]$StorageBackend = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
function Get-Sha256([string]$Value) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value)))).Replace('-','').ToLowerInvariant() } finally { $sha.Dispose() }
}
function Get-TargetHash([string]$Url) {
    return Get-Sha256 $Url.TrimEnd('/')
}
function Get-WorkspaceHash([string]$Path) {
    return Get-Sha256 ([System.IO.Path]::GetFullPath($Path).ToLowerInvariant())
}
function Get-ConfigIdentity([string]$TargetHash,[string]$ProxyHash,[string]$WorkspaceHash,[string]$Backend) {
    return Get-Sha256 "hyperkut-studio-config-v1`n$TargetHash`n$ProxyHash`n$WorkspaceHash`n$Backend"
}
function Read-Endpoint([string]$Url) {
    try { return Invoke-RestMethod -Uri $Url -TimeoutSec 2 } catch { return $null }
}
function Test-Listening([int]$ServicePort) {
    $tcp = New-Object System.Net.Sockets.TcpClient
    try { $task = $tcp.ConnectAsync('127.0.0.1',$ServicePort); return ($task.Wait(400) -and $tcp.Connected) } catch { return $false } finally { $tcp.Dispose() }
}
function Get-ProxyUploadLimit([int]$ServicePort) {
    try {
        $connection = Get-NetTCPConnection -LocalPort $ServicePort -State Listen -ErrorAction Stop | Select-Object -First 1
        if ($null -eq $connection) { return $null }
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction Stop
        $match = [regex]::Match([string]$process.CommandLine,'(?:^|\s)--max-upload-mb\s+(?:"(\d+)"|(\d+))(?:\s|$)')
        if (-not $match.Success) { return $null }
        if ($match.Groups[1].Success) { return [int]$match.Groups[1].Value }
        return [int]$match.Groups[2].Value
    } catch { return $null }
}
function Assert-ProxyTarget($Health,[string]$TargetHash,[int]$ServicePort) {
    if ($null -eq $Health -or $Health.status -ne 'healthy' -or -not $Health.upstream) {
        throw 'A healthy proxy is present, but its ComfyUI target cannot be verified; refusing to reuse it.'
    }
    if ((Get-TargetHash ([string]$Health.upstream)) -ne $TargetHash) {
        throw 'A healthy proxy is already present on this port, but it targets a different ComfyUI; no service was replaced.'
    }
    $uploadLimit = Get-ProxyUploadLimit $ServicePort
    if ($null -eq $uploadLimit) { throw 'The healthy proxy target matches, but its transfer limit cannot be verified; refusing to reuse it.' }
    if ($uploadLimit -ne 20512) { throw "The healthy proxy is configured for $uploadLimit MiB, not 20512 MiB; refusing to reuse it." }
}
function Assert-StudioIdentity($Status,[string]$TargetHash,[string]$ProxyHash,[string]$WorkspaceHash,[string]$Backend) {
    if (-not $Status.config_identity) {
        throw 'A healthy Studio is present but does not publish its configuration identity; refusing to reuse it.'
    }
    $actual = $Status.config_identity
    if ($actual.target_sha256 -ne $TargetHash) { throw 'The active Studio targets a different ComfyUI; refusing to reuse it.' }
    if ($actual.proxy_sha256 -ne $ProxyHash) { throw 'The active Studio uses a different SDK proxy; refusing to reuse it.' }
    if ($actual.workspace_sha256 -ne $WorkspaceHash) { throw 'The active Studio uses a different workspace; refusing to reuse it.' }
    if ($actual.storage_backend -ne $Backend) { throw 'The active Studio uses a different storage backend; refusing to reuse it.' }
    if ($actual.id -ne (Get-ConfigIdentity $TargetHash $ProxyHash $WorkspaceHash $Backend)) {
        throw 'The active Studio configuration identity does not match; refusing to reuse it.'
    }
}
if (-not $ProxyPort) {
    do {
        $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
        try {
            $listener.Start()
            $ProxyPort = [int]$listener.LocalEndpoint.Port
        } finally {
            $listener.Stop()
        }
    } while ($ProxyPort -eq $Port)
}
$comfy = if ($env:HYPERKUT_COMFYUI_URL) { [string]$env:HYPERKUT_COMFYUI_URL } else { $ComfyUI }
$comfy = $comfy.TrimEnd('/')
$env:HYPERKUT_COMFYUI_URL = $comfy
$workspaceValue = if ($Workspace) { $Workspace } elseif ($env:HYPERKUT_WORKSPACE) { [string]$env:HYPERKUT_WORKSPACE } elseif ($env:SECATOR_WORKSPACE) { [string]$env:SECATOR_WORKSPACE } else { Join-Path $root 'workspace' }
if (-not [System.IO.Path]::IsPathRooted($workspaceValue)) { $workspaceValue = Join-Path $root $workspaceValue }
$Workspace = [System.IO.Path]::GetFullPath($workspaceValue)
$env:HYPERKUT_WORKSPACE = $Workspace
$backend = if ($StorageBackend) { $StorageBackend } elseif ($env:HYPERKUT_STORAGE_BACKEND) { [string]$env:HYPERKUT_STORAGE_BACKEND } elseif ($env:SECATOR_STORAGE_BACKEND) { [string]$env:SECATOR_STORAGE_BACKEND } else { 'shared_local' }
$env:HYPERKUT_STORAGE_BACKEND = $backend
$targetHash = Get-TargetHash $comfy
$env:COMFY_BASE_URL = "http://127.0.0.1:$ProxyPort"
$proxyHash = Get-TargetHash $env:COMFY_BASE_URL
$workspaceHash = Get-WorkspaceHash $Workspace
if ($OutputDir) { $env:HYPERKUT_OUTPUT_DIR = (Resolve-Path -LiteralPath $OutputDir).Path }
$proxyHealth = "http://127.0.0.1:$ProxyPort/api/v2/health"
$proxyStatus = Read-Endpoint $proxyHealth
if ($proxyStatus -and $proxyStatus.status -eq 'healthy') {
    Assert-ProxyTarget $proxyStatus $targetHash $ProxyPort
} elseif (Test-Listening $ProxyPort) {
    throw "Port $ProxyPort is occupied by a service that is not a verifiable Comfy proxy."
}
$studioStatusUrl = "http://127.0.0.1:$Port/api/studio/status"
$studioStatus = Read-Endpoint $studioStatusUrl
if ($studioStatus -and $studioStatus.instance_id) {
    Assert-StudioIdentity $studioStatus $targetHash $proxyHash $workspaceHash $backend
    if ($studioStatus.restarting) { throw 'The matching Studio is restarting; retry when it is ready.' }
    Write-Output "HyperKut Studio already matches this configuration: http://127.0.0.1:$Port/"
    return
} elseif (Test-Listening $Port) {
    throw "Port $Port is occupied by a service that is not a verifiable HyperKut Studio."
}
Push-Location -LiteralPath $root
try {
    if (-not ($proxyStatus -and $proxyStatus.status -eq 'healthy')) {
        & "$root\.venv\Scripts\comfy-api-proxy.exe" start --comfyui $comfy --port $ProxyPort --max-upload-mb 20512
        if ($LASTEXITCODE -ne 0) { throw 'The Comfy API proxy could not start. Check comfy-api-proxy status.' }
        $deadline = (Get-Date).AddSeconds(40)
        do { $proxyStatus = Read-Endpoint $proxyHealth; if (-not $proxyStatus) { Start-Sleep -Milliseconds 250 } } while (-not $proxyStatus -and (Get-Date) -lt $deadline)
    }
    Assert-ProxyTarget $proxyStatus $targetHash $ProxyPort
    Write-Output "Proxy upload ceiling: 20512 MiB; Studio uploads: up to 1 GiB; project artifacts: 2 GiB per blob / 20 GiB cache."
    & "$root\.venv\Scripts\python.exe" -m uvicorn backend.server:create_app --factory --host 127.0.0.1 --port $Port
} finally {
    Pop-Location
}
