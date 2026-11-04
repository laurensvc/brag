# Builds Brag for Windows: dist\Brag\Brag.exe (PyInstaller) and dist\BragSetup.exe (Inno Setup).
# Once:  py -m pip install -r windows\requirements.txt
#        winget install JRSoftware.InnoSetup        (only for the installer; without it you still get Brag.exe)
# Then:  .\windows\build.ps1
# The release workflow runs this same script on a Windows runner.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$build = Join-Path $root 'build'
$dist = Join-Path $root 'dist'
$py = if ($env:GITHUB_ACTIONS -or -not (Get-Command py -ErrorAction SilentlyContinue)) { 'python' } else { 'py' }  # CI: setup-python's

function Run {
  & $args[0] $args[1..($args.Count - 1)]
  if ($LASTEXITCODE) { throw "$($args[0]) failed (exit code $LASTEXITCODE)" }
}

$version = (Select-String -Path (Join-Path $root 'Brag\Brag.toc') -Pattern '^## Version:\s*(\S+)').Matches[0].Groups[1].Value
Write-Host "Building Brag $version"
New-Item -ItemType Directory -Force $build | Out-Null
Remove-Item -Recurse -Force (Join-Path $dist 'Brag'), (Join-Path $dist 'BragSetup.exe') -ErrorAction SilentlyContinue

Run $py (Join-Path $root 'companion\desktop.py') --write-icon (Join-Path $build 'brag.ico')
Run $py -m PyInstaller --noconfirm --clean --windowed --name Brag `
  --icon (Join-Path $build 'brag.ico') `
  --add-data "$(Join-Path $root 'companion\index.html');." `
  --add-data "$(Join-Path $root 'companion\assets');assets" `
  --hidden-import pystray._win32 `
  --distpath $dist --workpath (Join-Path $build 'pyinstaller') --specpath $build `
  (Join-Path $root 'companion\desktop.py')
Write-Host "Built $dist\Brag\Brag.exe"

$iscc = @(
  (Get-Command iscc -ErrorAction SilentlyContinue).Source,
  "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) {
  Write-Warning 'Inno Setup not found, so no installer. Get it with: winget install JRSoftware.InnoSetup'
  exit 0
}
Run $iscc /Qp "/DAppVersion=$version" "/DSourceDir=$dist\Brag" "/DOutputDir=$dist" "/DIconFile=$build\brag.ico" (Join-Path $PSScriptRoot 'brag.iss')
Write-Host "Built $dist\BragSetup.exe"
