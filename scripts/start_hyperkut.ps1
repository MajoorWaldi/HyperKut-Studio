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
function Is-Listening([int]$ServicePort) {
  $tcp=New-Object System.Net.Sockets.TcpClient
  try { $task=$tcp.ConnectAsync('127.0.0.1',$ServicePort); return ($task.Wait(400) -and $tcp.Connected) } catch { return $false } finally { $tcp.Dispose() }
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
  if (-not $ProxyPort) { $ProxyPort=[int]$config.proxy_port }
  if ($Port -lt 1024 -or $Port -gt 65535 -or $ProxyPort -lt 1024 -or $ProxyPort -gt 65535 -or $Port -eq $ProxyPort) { throw 'Ports du lanceur invalides.' }
  $mutex=New-Object System.Threading.Mutex($false,"Local\HyperKutStudioLauncher_$Port")
  $ownsMutex=$mutex.WaitOne(0)
  if (-not $ownsMutex) { return }
  $comfy=[string]$config.comfyui_url
  $env:HYPERKUT_COMFYUI_URL=$comfy
  $env:COMFY_BASE_URL="http://127.0.0.1:$ProxyPort"
  $workspace=[string]$config.workspace
  if (-not [System.IO.Path]::IsPathRooted($workspace)) { $workspace=Join-Path $root $workspace }
  $env:HYPERKUT_WORKSPACE=$workspace
  if ($config.output_dir) { $env:HYPERKUT_OUTPUT_DIR=[string]$config.output_dir }
  if ($config.env) { foreach ($property in $config.env.PSObject.Properties) { [Environment]::SetEnvironmentVariable($property.Name,[string]$property.Value,'Process') } }
  $logDir=Join-Path $workspace 'logs'
  New-Item -ItemType Directory -Force -Path $logDir | Out-Null
  $proxyHealth="http://127.0.0.1:$ProxyPort/api/v2/health"
  if (-not (Is-Ready $proxyHealth 'proxy')) {
    if (Is-Listening $ProxyPort) { throw "Le port $ProxyPort est occupé par un service qui ne répond pas comme le proxy Comfy." }
    Start-Process -FilePath $python -ArgumentList @('-m','comfy_api_proxy.cli','run','--comfyui',$comfy,'--host','127.0.0.1','--port',"$ProxyPort",'--max-upload-mb','100') -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir "launcher-proxy-$ProxyPort-out.log") -RedirectStandardError (Join-Path $logDir "launcher-proxy-$ProxyPort-err.log")
    Wait-Ready $proxyHealth 'proxy'
  }
  $url="http://127.0.0.1:$Port/"
  $status="http://127.0.0.1:$Port/api/studio/status"
  if (-not (Is-Ready $status 'studio')) {
    if (Is-Listening $Port) { throw "Le port $Port est occupé par un service qui ne répond pas comme HyperKut." }
    Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','backend.server:create_app','--factory','--host','127.0.0.1','--port',"$Port") -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir "launcher-studio-$Port-out.log") -RedirectStandardError (Join-Path $logDir "launcher-studio-$Port-err.log")
    Wait-Ready $status 'studio'
  }
  if (-not $NoBrowser) { Start-Process -FilePath $url }
  Write-Output "HyperKut Studio prêt : $url"
} catch {
  if ($NoBrowser) { throw }
  Add-Type -AssemblyName PresentationFramework
  [System.Windows.MessageBox]::Show($_.Exception.Message,'HyperKut Studio',0,16) | Out-Null
} finally {
  if ($ownsMutex) { $mutex.ReleaseMutex() }
  if ($mutex) { $mutex.Dispose() }
}
