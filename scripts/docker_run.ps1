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

Write-Host "Building image $Image..."
docker build -t $Image $Root

try {
  docker rm -f $Container | Out-Null
} catch {
}

Write-Host "Starting container $Container on port 7003..."
docker run -d --name $Container `
  -p 7003:7003 `
  -e HOST=0.0.0.0 `
  -e PORT=7003 `
  -v "$($DataDir):/app/data" `
  $Image | Out-Null

Write-Host "Done. Open http://127.0.0.1:7003"
