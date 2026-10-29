param([int]$Port=0, [int]$ProxyPort=0, [string]$SettingsFile='', [switch]$NoBrowser)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$python=Join-Path $root '.venv\Scripts\python.exe'
if (-not $SettingsFile) {
  $SettingsFile=Join-Path $PSScriptRoot 'launcher\settings.json'
  if (-not (Test-Path -LiteralPath $SettingsFile)) { $SettingsFile=Join-Path $PSScriptRoot 'launcher\settings.example.json' }
}
$mutex=$null; $ownsMutex=$false
function Read-Endpoint([string]$Url) {
  try { return Invoke-RestMethod -Uri $Url -TimeoutSec 2 } catch { return $null }
}
function Is-Ready([string]$Url,[string]$Kind) {
  $value=Read-Endpoint $Url
  if ($Kind -eq 'studio') { return ($null -ne $value -and [bool]$value.instance_id) }
  return ($null -ne $value -and $value.status -eq 'healthy')
}
function Get-Sha256([string]$Value) {
  $sha=[System.Security.Cryptography.SHA256]::Create()
  try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value)))).Replace('-','').ToLowerInvariant() } finally { $sha.Dispose() }
}
function Get-TargetHash([string]$Url) {
  return Get-Sha256 $Url.TrimEnd('/')
}
function Get-WorkspaceHash([string]$Path) {
  $full=[System.IO.Path]::GetFullPath($Path).ToLowerInvariant()
  return Get-Sha256 $full
}
function Get-ConfigIdentity([string]$TargetHash,[string]$ProxyHash,[string]$WorkspaceHash,[string]$Backend) {
  return Get-Sha256 "hyperkut-studio-config-v1`n$TargetHash`n$ProxyHash`n$WorkspaceHash`n$Backend"
}
function Get-ProxyUploadLimit([int]$ServicePort) {
  try {
    $connection=Get-NetTCPConnection -LocalPort $ServicePort -State Listen -ErrorAction Stop | Select-Object -First 1
    if ($null -eq $connection) { return $null }
    $process=Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction Stop
    $match=[regex]::Match([string]$process.CommandLine,'(?:^|\s)--max-upload-mb\s+(?:"(\d+)"|(\d+))(?:\s|$)')
    if (-not $match.Success) { return $null }
    if ($match.Groups[1].Success) { return [int]$match.Groups[1].Value }
    return [int]$match.Groups[2].Value
  } catch { return $null }
}
function Assert-ProxyTarget($Health,[string]$TargetHash,[int]$ServicePort) {
  if ($null -eq $Health -or $Health.status -ne 'healthy' -or -not $Health.upstream) {
    throw 'Un proxy est joignable mais son identité de cible ne peut pas être vérifiée ; refus de le réutiliser.'
  }
  if ((Get-TargetHash ([string]$Health.upstream)) -ne $TargetHash) {
    throw 'Un proxy sain est deja present sur ce port, mais sa cible ComfyUI differe de la configuration demandee ; aucun service n''a ete remplace.'
  }
  $uploadLimit=Get-ProxyUploadLimit $ServicePort
  if ($null -eq $uploadLimit) { throw 'Un proxy sain cible le bon ComfyUI, mais son plafond de transfert ne peut pas être vérifié ; refus de le réutiliser.' }
  if ($uploadLimit -ne 20512) { throw "Le proxy sain est configuré pour $uploadLimit MiB, au lieu de 20512 MiB ; refus de le réutiliser." }
}
function Assert-StudioIdentity($Status,$Expected) {
  if (-not $Status.config_identity) {
    throw 'Un Studio sain est déjà présent, mais il ne publie pas son identité de configuration ; refus de le réutiliser.'
  }
  $actual=$Status.config_identity
  if ($actual.target_sha256 -ne $Expected.target_sha256) {
    throw 'Le Studio déjà actif cible un autre ComfyUI ; refus de le réutiliser.'
  }
  if ($actual.proxy_sha256 -ne $Expected.proxy_sha256) {
    throw 'Le Studio déjà actif utilise un autre proxy SDK ; refus de le réutiliser.'
  }
  if ($actual.workspace_sha256 -ne $Expected.workspace_sha256) {
    throw 'Le Studio déjà actif utilise un autre espace de travail ; refus de le réutiliser.'
  }
  if ($actual.storage_backend -ne $Expected.storage_backend) {
    throw 'Le Studio déjà actif utilise un autre backend de stockage ; refus de le réutiliser.'
  }
  if ($actual.id -ne $Expected.id) {
    throw 'L''identite de configuration du Studio actif ne correspond pas ; refus de le reutiliser.'
  }
}
function Is-Listening([int]$ServicePort) {
  $tcp=New-Object System.Net.Sockets.TcpClient
  try { $task=$tcp.ConnectAsync('127.0.0.1',$ServicePort); return ($task.Wait(400) -and $tcp.Connected) } catch { return $false } finally { $tcp.Dispose() }
}
function Get-FreeLoopbackPort([int]$ExcludedPort) {
  do {
    $listener=New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback,0)
    try { $listener.Start(); $candidate=[int]$listener.LocalEndpoint.Port } finally { $listener.Stop() }
  } while ($candidate -eq $ExcludedPort)
  return $candidate
}
function Wait-Ready([string]$Url,[string]$Kind) {
  $deadline=(Get-Date).AddSeconds(40)
  do { if (Is-Ready $Url $Kind) { return }; Start-Sleep -Milliseconds 250 } while ((Get-Date) -lt $deadline)
  throw "Le service $Kind ne répond pas. Consulte les journaux dans $logDir."
}
try {
  if (-not (Test-Path -LiteralPath $python)) { throw 'Python du Studio introuvable.' }
  $config=Get-Content -LiteralPath $SettingsFile -Raw | ConvertFrom-Json
  if (-not $Port) { $Port=[int]$config.studio_port }
  $proxyPortWasExplicit=($ProxyPort -ne 0)
  if (-not $proxyPortWasExplicit) { $ProxyPort=[int]$config.proxy_port }
  if ($Port -lt 1024 -or $Port -gt 65535 -or $ProxyPort -lt 1024 -or $ProxyPort -gt 65535 -or $Port -eq $ProxyPort) { throw 'Ports du lanceur invalides.' }
  $mutex=New-Object System.Threading.Mutex($false,"Local\HyperKutStudioLauncher_$Port")
  $ownsMutex=$mutex.WaitOne(0)
  if (-not $ownsMutex) { return }
  $comfy=[string]$config.comfyui_url
  $env:HYPERKUT_COMFYUI_URL=$comfy.TrimEnd('/')
  $env:COMFY_BASE_URL="http://127.0.0.1:$ProxyPort"
  $workspace=[string]$config.workspace
  if (-not [System.IO.Path]::IsPathRooted($workspace)) { $workspace=Join-Path $root $workspace }
  $env:HYPERKUT_WORKSPACE=[System.IO.Path]::GetFullPath($workspace)
  if ($config.output_dir) { $env:HYPERKUT_OUTPUT_DIR=[string]$config.output_dir }
  if ($config.env) { foreach ($property in $config.env.PSObject.Properties) { [Environment]::SetEnvironmentVariable($property.Name,[string]$property.Value,'Process') } }
  $comfy=[string]$env:HYPERKUT_COMFYUI_URL
  if (-not $comfy) { $comfy=[string]$env:SECATOR_COMFYUI_URL }
  if (-not $comfy) { throw 'La cible ComfyUI est absente de la configuration.' }
  $comfy=$comfy.TrimEnd('/')
  $env:HYPERKUT_COMFYUI_URL=$comfy
  $workspace=[string]$env:HYPERKUT_WORKSPACE
  if (-not $workspace) { $workspace=[string]$env:SECATOR_WORKSPACE }
  if (-not $workspace) { $workspace=Join-Path $root 'workspace' }
  if (-not [System.IO.Path]::IsPathRooted($workspace)) { $workspace=Join-Path $root $workspace }
  $workspace=[System.IO.Path]::GetFullPath($workspace)
  $env:HYPERKUT_WORKSPACE=$workspace
  $backend=[string]$env:HYPERKUT_STORAGE_BACKEND
  if (-not $backend) { $backend=[string]$env:SECATOR_STORAGE_BACKEND }
  if (-not $backend) { $backend='shared_local' }
  if ($backend -notin @('shared_local','remote_artifacts')) { throw 'Backend de stockage inconnu dans la configuration.' }
  $env:HYPERKUT_STORAGE_BACKEND=$backend
  $targetHash=Get-TargetHash $comfy
  $logDir=Join-Path $workspace 'logs'
  New-Item -ItemType Directory -Force -Path $logDir | Out-Null
  $proxyHealth="http://127.0.0.1:$ProxyPort/api/v2/health"
  $proxyStatus=Read-Endpoint $proxyHealth
  if ($null -ne $proxyStatus -and $proxyStatus.status -eq 'healthy') {
    Assert-ProxyTarget $proxyStatus $targetHash $ProxyPort
  } elseif (Is-Listening $ProxyPort) {
    if ($proxyPortWasExplicit) { throw "Le port $ProxyPort est occupé par un service qui ne répond pas comme le proxy Comfy." }
    $ProxyPort=Get-FreeLoopbackPort $Port
    $proxyHealth="http://127.0.0.1:$ProxyPort/api/v2/health"
  }
  $env:COMFY_BASE_URL="http://127.0.0.1:$ProxyPort"
  $proxyHash=Get-TargetHash $env:COMFY_BASE_URL
  $workspaceHash=Get-WorkspaceHash $workspace
  $expectedIdentity=[PSCustomObject]@{
    target_sha256=$targetHash
    proxy_sha256=$proxyHash
    workspace_sha256=$workspaceHash
    storage_backend=$backend
    id=(Get-ConfigIdentity $targetHash $proxyHash $workspaceHash $backend)
  }
  if (-not (Is-Ready $proxyHealth 'proxy')) {
    Start-Process -FilePath $python -ArgumentList @('-m','comfy_api_proxy.cli','run','--comfyui',$comfy,'--host','127.0.0.1','--port',"$ProxyPort",'--max-upload-mb','20512') -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir "launcher-proxy-$ProxyPort-out.log") -RedirectStandardError (Join-Path $logDir "launcher-proxy-$ProxyPort-err.log")
    Wait-Ready $proxyHealth 'proxy'
    Assert-ProxyTarget (Read-Endpoint $proxyHealth) $targetHash $ProxyPort
  }
  $url="http://127.0.0.1:$Port/"
  $status="http://127.0.0.1:$Port/api/studio/status"
  $studioStatus=Read-Endpoint $status
  if ($null -ne $studioStatus -and $studioStatus.instance_id) {
    Assert-StudioIdentity $studioStatus $expectedIdentity
    if ($studioStatus.restarting) { throw 'Le Studio correspondant est en cours de redemarrage ; reessayez quand il sera pret.' }
  } else {
    if (Is-Listening $Port) { throw "Le port $Port est occupé par un service qui ne répond pas comme HyperKut." }
    Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','backend.server:create_app','--factory','--host','127.0.0.1','--port',"$Port") -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir "launcher-studio-$Port-out.log") -RedirectStandardError (Join-Path $logDir "launcher-studio-$Port-err.log")
    Wait-Ready $status 'studio'
    Assert-StudioIdentity (Read-Endpoint $status) $expectedIdentity
  }
  if (-not $NoBrowser) { Start-Process -FilePath $url }
  Write-Output "HyperKut Studio prêt : $url (proxy : 127.0.0.1:$ProxyPort, 20512 MiB/upload ; Studio : 1 GiB/upload ; assets : 2 GiB/blob, 20 GiB/cache)"
} catch {
  if ($NoBrowser) { throw }
  Add-Type -AssemblyName PresentationFramework
  [System.Windows.MessageBox]::Show($_.Exception.Message,'HyperKut Studio',0,16) | Out-Null
} finally {
  if ($ownsMutex) { $mutex.ReleaseMutex() }
  if ($mutex) { $mutex.Dispose() }
}
