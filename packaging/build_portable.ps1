# Builds the portable QuIIN folder (PyInstaller onedir), runs the launch
# smoke test and zips dist\QuIIN to dist\QuIIN-Portable-<AAAA-MM-DD>.zip.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    & ".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
    if (-not $?) { throw "pip install failed" }

    & ".venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm packaging\quiin.spec
    if (-not $?) { throw "PyInstaller build failed" }

    & ".venv\Scripts\python.exe" packaging\smoke_test.py
    if (-not $?) { throw "Smoke test failed" }

    # Não empacotar o log do smoke.
    if (Test-Path -LiteralPath "dist\QuIIN\console.txt") {
        Remove-Item -LiteralPath "dist\QuIIN\console.txt"
    }

    $stamp = Get-Date -Format "yyyy-MM-dd"
    $zip = "dist\QuIIN-Portable-$stamp.zip"
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip }
    # tar.exe (bsdtar, nativo do Windows 10+): muito mais rápido que
    # Compress-Archive, que leva muitos minutos em pastas de ~300 MB.
    & tar.exe -a -c -f $zip -C dist QuIIN
    if (-not $?) { throw "Zip creation failed" }
    Write-Host "Portable package ready: $zip"
}
finally {
    Pop-Location
}
