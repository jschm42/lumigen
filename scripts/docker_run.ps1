$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot\.."
$Image = "img-hub:latest"
$Container = "img-hub"
$DataDir = Join-Path $Root "data"

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
