$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot\.."
$SslDir = Join-Path $Root "ssl"
$CertFile = Join-Path $SslDir "lumigen.crt"
$KeyFile = Join-Path $SslDir "lumigen.key"
$Days = 3650

if (-not (Test-Path $SslDir)) {
  New-Item -ItemType Directory -Path $SslDir | Out-Null
}

if ((Test-Path $CertFile) -or (Test-Path $KeyFile)) {
  Write-Host "WARNING: SSL certificate or key already exists in $SslDir"
  Write-Host "  Cert: $CertFile"
  Write-Host "  Key:  $KeyFile"
  Write-Host ""
  Write-Host "Remove them first if you want to regenerate:"
  Write-Host "  Remove-Item '$CertFile','$KeyFile'"
  exit 1
}

if (-not (Get-Command openssl -ErrorAction SilentlyContinue)) {
  Write-Host "ERROR: openssl is not installed. Install it first:"
  Write-Host "  winget install ShiningLight.OpenSSL"
  Write-Host "  or: choco install openssl"
  Write-Host "  or download from https://slproweb.com/products/Win32OpenSSL.html"
  exit 1
}

Write-Host "Generating self-signed SSL certificate (valid for $Days days)..."

$Subject = "/C=DE/ST=NRW/L=Cologne/O=Lumigen/OU=Dev/CN=localhost"

& openssl req -x509 -nodes -days $Days -newkey rsa:2048 `
  -keyout $KeyFile `
  -out $CertFile `
  -subj $Subject `
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>$null

if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR: openssl failed to generate the certificate."
  exit 1
}

Write-Host ""
Write-Host "Self-signed certificate generated successfully."
Write-Host "  Certificate: $CertFile"
Write-Host "  Private key: $KeyFile"
Write-Host ""
Write-Host "Add these lines to your .env file to enable HTTPS:"
Write-Host "  SSL_CERT_FILE=$CertFile"
Write-Host "  SSL_KEY_FILE=$KeyFile"
Write-Host ""
Write-Host "NOTE: Browsers will show a security warning for self-signed certificates."
Write-Host "      Click 'Advanced' -> 'Proceed to localhost' to accept it."