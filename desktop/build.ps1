<#
.SYNOPSIS
    Compila MacropadFX.exe (PyInstaller one-dir, sin consola).

.DESCRIPTION
    1) genera icon.ico con make_icon.py (si falta),
    2) instala PyInstaller si no esta,
    3) limpia build/ y dist/,
    4) compila MacropadFX.spec y reporta tamanos.

.PARAMETER SkipIcon
    No regenerar icon.ico (usar el que ya este).

.PARAMETER NoClean
    No borrar build/ ni dist/ antes de compilar.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\build.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipIcon,
    [switch]$NoClean
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location -LiteralPath $here

function Info([string]$m) { Write-Host "[build] $m" -ForegroundColor Cyan }
function Die([string]$m) { Write-Host "[build] ERROR: $m" -ForegroundColor Red; exit 1 }

# 0) Python
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { Die "No se encontro 'python' en el PATH." }
$python = $py.Source
Info "python: $python"

# 1) icono
if (-not $SkipIcon -or -not (Test-Path -LiteralPath "icon.ico")) {
    Info "generando icon.ico ..."
    & $python make_icon.py
    if ($LASTEXITCODE -ne 0) { Die "make_icon.py fallo (exit $LASTEXITCODE)." }
}
if (-not (Test-Path -LiteralPath "icon.ico")) { Die "falta icon.ico." }

# 2) PyInstaller
& $python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Info "instalando PyInstaller ..."
    & $python -m pip install --upgrade pyinstaller
    if ($LASTEXITCODE -ne 0) { Die "no se pudo instalar PyInstaller." }
}
$pv = (& $python -c "import PyInstaller; print(PyInstaller.__version__)").Trim()
Info "PyInstaller $pv"

# 3) limpieza
if (-not $NoClean) {
    foreach ($d in @("build", "dist")) {
        if (Test-Path -LiteralPath $d) {
            Info "limpiando $d\"
            Remove-Item -LiteralPath $d -Recurse -Force
        }
    }
}

# 4) compilar
Info "compilando (PyInstaller one-dir, windowed) ..."
& $python -m PyInstaller --noconfirm --clean MacropadFX.spec
if ($LASTEXITCODE -ne 0) { Die "PyInstaller fallo (exit $LASTEXITCODE)." }

# 5) reporte
$exe = Join-Path $here "dist\MacropadFX\MacropadFX.exe"
if (-not (Test-Path -LiteralPath $exe)) { Die "no se genero $exe." }
$exeSize = (Get-Item -LiteralPath $exe).Length
$dirSize = (Get-ChildItem -LiteralPath "dist\MacropadFX" -Recurse -File |
    Measure-Object -Property Length -Sum).Sum
Info ("exe  -> {0}  ({1:N2} MB)" -f $exe, ($exeSize / 1MB))
Info ("dist -> {0}  ({1:N2} MB)" -f (Join-Path $here "dist\MacropadFX"), ($dirSize / 1MB))
Info "listo. Instalador: ISCC.exe installer.iss"
