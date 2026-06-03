$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot\.."
$Image = "lumigen:latest"
$Container = "lumigen"
$EnvFile = Join-Path $Root ".env"
$EnvMap = @{}

if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object { $_.Trim() } | Where-Object {
    $_ -and -not $_.StartsWith("#")
  } | ForEach-Object {
    $parts = $_ -split "=", 2
    if ($parts.Length -eq 2) {
      $EnvMap[$parts[0].Trim()] = $parts[1].Trim()
    }
  }
}

$HostValue = $EnvMap["HOST"]
if ([string]::IsNullOrWhiteSpace($HostValue)) { $HostValue = "0.0.0.0" }

$PortValue = $EnvMap["PORT"]
if ([string]::IsNullOrWhiteSpace($PortValue)) { $PortValue = "7003" }

$DataDirValue = $EnvMap["DOCKER_DATA_DIR"]
if ([string]::IsNullOrWhiteSpace($DataDirValue)) {
  $DataDir = Join-Path $Root "data"
} elseif ([System.IO.Path]::IsPathRooted($DataDirValue)) {
  $DataDir = $DataDirValue
} else {
  $DataDir = Join-Path $Root $DataDirValue
}

if (-not (Test-Path $DataDir)) {
  New-Item -ItemType Directory -Path $DataDir | Out-Null
}

Write-Host "Pulling latest changes from git..."
Push-Location $Root
try {
  git pull
} finally {
  Pop-Location
}

Write-Host "Building image $Image..."
docker build -t $Image $Root

try {
  docker rm -f $Container | Out-Null
} catch {
}

Write-Host "Starting container $Container on port $PortValue..."
$EnvArgs = @()
function Add-OptionalEnvArg {
  param(
    [string]$Key
  )
  $Value = $EnvMap[$Key]
  if (-not [string]::IsNullOrWhiteSpace($Value)) {
    $EnvArgs += "-e"
    $EnvArgs += "$Key=$Value"
  }
}

Add-OptionalEnvArg "PROVIDER_CONFIG_KEY"
Add-OptionalEnvArg "SESSION_HTTPS_ONLY"
Add-OptionalEnvArg "PROXY_HEADERS_ENABLED"
Add-OptionalEnvArg "PROXY_HEADERS_TRUSTED_HOSTS"

$EnvFileArgs = @()
if (Test-Path $EnvFile) {
  $EnvFileArgs += "--env-file"
  $EnvFileArgs += $EnvFile
}

$SslCertFile = $EnvMap["SSL_CERT_FILE"]
$SslKeyFile = $EnvMap["SSL_KEY_FILE"]
$SslMountArgs = @()
$SslCertArg = ""
$SslKeyArg = ""

if (-not [string]::IsNullOrWhiteSpace($SslCertFile) -and -not [string]::IsNullOrWhiteSpace($SslKeyFile)) {
  if (-not (Test-Path $SslCertFile)) {
    Write-Error "SSL_CERT_FILE not found: $SslCertFile"
  }
  if (-not (Test-Path $SslKeyFile)) {
    Write-Error "SSL_KEY_FILE not found: $SslKeyFile"
  }
  $SslMountArgs += "-v"
  $SslMountArgs += "${SslCertFile}:/etc/ssl/certs/lumigen.crt:ro"
  $SslMountArgs += "-v"
  $SslMountArgs += "${SslKeyFile}:/etc/ssl/private/lumigen.key:ro"
  $SslCertArg = "/etc/ssl/certs/lumigen.crt"
  $SslKeyArg = "/etc/ssl/private/lumigen.key"
}

$RunArgs = @(
  "run", "-d", "--name", $Container,
  "-p", "${PortValue}:$PortValue",
  "-e", "HOST=$HostValue",
  "-e", "PORT=$PortValue",
  "-e", "SSL_CERT_FILE=$SslCertArg",
  "-e", "SSL_KEY_FILE=$SslKeyArg"
)

if ($EnvFileArgs.Count -gt 0) {
  $RunArgs += $EnvFileArgs
}
if ($EnvArgs.Count -gt 0) {
  $RunArgs += $EnvArgs
}
if ($SslMountArgs.Count -gt 0) {
  $RunArgs += $SslMountArgs
}

$RunArgs += "-v"
$RunArgs += "$($DataDir):/app/data"
$RunArgs += $Image

& docker $RunArgs | Out-Null

$Proto = "http"
if (-not [string]::IsNullOrWhiteSpace($SslCertFile) -and -not [string]::IsNullOrWhiteSpace($SslKeyFile)) {
  $Proto = "https"
}
Write-Host "Done. Open ${Proto}://127.0.0.1:$PortValue"