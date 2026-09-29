<#
.SYNOPSIS
  Starts the MMAC study hub: the website and the health-screening app, each
  in its own window. The Streamlit capture dashboards are for recording
  sessions and are no longer linked from the site; -Dashboards starts them too.

.EXAMPLE
  .\start-hub.ps1                 # website + health screening
  .\start-hub.ps1 -SkipHealth     # just the website
  .\start-hub.ps1 -Dashboards     # also the Streamlit capture dashboards

  Website            http://localhost:3000   (/thermal, /ecg data pages)
  Health screening   http://localhost:5174   (API on 4100)
  Dashboards         Thermal :8501 · ECG :8502 · SpO2 :8503   (with -Dashboards)
#>
param(
  [switch]$Dashboards,
  [switch]$SkipHealth
)

$root = $PSScriptRoot

function Start-InWindow($title, $dir, $command) {
  $script = "`$Host.UI.RawUI.WindowTitle = '$title'; Set-Location '$dir'; $command"
  Start-Process powershell -ArgumentList '-NoExit', '-Command', $script
  Write-Host "  started $title"
}

function Install-IfMissing($dir) {
  if (-not (Test-Path (Join-Path $dir 'node_modules'))) {
    Write-Host "  installing dependencies in $dir ..."
    Push-Location $dir
    npm install --no-audit --no-fund
    Pop-Location
  }
}

Write-Host 'MMAC study hub'

$website = Join-Path $root 'website'
Install-IfMissing $website
Start-InWindow 'MMAC website :3000' $website 'npm run dev'

if (-not $SkipHealth) {
  $server = Join-Path $root 'health-screening\server'
  $client = Join-Path $root 'health-screening\client'
  if (-not (Test-Path (Join-Path $server '.env'))) {
    Write-Warning 'health-screening\server\.env is missing - see health-screening\README.md. Skipping health screening.'
  } else {
    Install-IfMissing $server
    Install-IfMissing $client
    Start-InWindow 'Health screening API :4100' $server 'npm start'
    Start-InWindow 'Health screening :5174' $client 'npm run dev'
  }
}

if ($Dashboards) {
  # Each folder's .streamlit/config.toml pins its port, so they run from
  # inside their own folder. Thermal ships its own venv; the others use the
  # streamlit on PATH.
  foreach ($sensor in 'Thermal', 'ECG', 'SpO2') {
    $dir = Join-Path $root $sensor
    $venvStreamlit = Join-Path $dir '.venv\Scripts\streamlit.exe'
    $streamlit = if (Test-Path $venvStreamlit) { "& '$venvStreamlit'" } else { 'streamlit' }
    Start-InWindow "$sensor dashboard" $dir "$streamlit run dashboard.py --server.headless true"
  }
}

Write-Host ''
Write-Host 'Open http://localhost:3000 once the website window says Ready.'
