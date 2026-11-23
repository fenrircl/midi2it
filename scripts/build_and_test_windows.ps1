param(
    [string]$MidiPath = "examples\forest-night-fever.mid",
    [string]$Sf2Path = "",
    [string]$OutputPath = "build\local-validation.it",
    [ValidateSet("onedir", "onefile")]
    [string]$BuildMode = "onedir",
    [switch]$Gui,
    [switch]$BuildOnly,
    [switch]$SkipBuild,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
$launchGui = $Gui -or [string]::IsNullOrWhiteSpace($Sf2Path)

function Resolve-RepoPath([string]$Path) {
    if ([System.IO.Path]::IsPathRooted($Path)) { return $Path }
    return Join-Path $repoRoot $Path
}

function Invoke-Conversion([string]$Executable, [string]$Midi, [string]$SoundFont, [string]$Output) {
    # El writer aplica el presupuesto BRR también fuera de --snes. Evitamos
    # el límite PCM conservador de ese modo, que puede recortar soundfonts normales.
    $arguments = @($Midi, $SoundFont, "--output", $Output)
    Write-Host "`nGenerando IT con: $Executable $($arguments -join ' ')" -ForegroundColor Cyan
    & $Executable @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "La conversión terminó con código $LASTEXITCODE. Revisa las rutas y el presupuesto BRR."
    }
    if (-not (Test-Path $Output)) { throw "No se creó el archivo esperado: $Output" }
}

$venv = Join-Path $repoRoot ".venv-win"
$venvPython = Join-Path $venv "Scripts\python.exe"
$createdVenv = $false
if (-not (Test-Path $venvPython)) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        & $launcher.Source -3 -m venv $venv
    } else {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) { throw "Instala Python 3 y vuelve a ejecutar este script." }
        & $python.Source -m venv $venv
    }
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno virtual en $venv" }
    $createdVenv = $true
}

if (-not $SkipInstall) {
    $packagesReady = $false
    if (-not $createdVenv) {
        & $venvPython -c "import mido, PyInstaller"
        $packagesReady = ($LASTEXITCODE -eq 0)
    }
    if ($createdVenv -or -not $packagesReady) {
        Write-Host "Preparando dependencias Python en .venv-win..." -ForegroundColor Cyan
        & $venvPython -m pip install -r (Join-Path $repoRoot "requirements.txt") pyinstaller
        if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de dependencias" }
    } else {
        Write-Host "Dependencias Python ya listas; se omite la instalación." -ForegroundColor Green
    }
} else {
    Write-Host "-SkipInstall: se omite la comprobación e instalación Python." -ForegroundColor Yellow
}

$builtExecutable = $null
if (-not $SkipBuild) {
    $modePath = Join-Path $repoRoot "dist\$BuildMode"
    $workPath = Join-Path $repoRoot "build\pyinstaller-$BuildMode"
    $exampleData = "$(Join-Path $repoRoot 'examples');examples"
    $windowMode = if ($launchGui) { "--windowed" } else { "--console" }
    $buildArgs = @(
        "-m", "PyInstaller", "--clean", "--noconfirm", "--$BuildMode", $windowMode,
        "--name", "midi2it", "--paths", $repoRoot,
        "--distpath", $modePath, "--workpath", $workPath,
        "--add-data", $exampleData,
        "--collect-submodules", "core", "--collect-submodules", "gui",
        "--hidden-import", "midi2it_gui", "--hidden-import", "mido", "midi2it.py"
    )
    Write-Host "`nGenerando build Windows ($BuildMode)..." -ForegroundColor Cyan
    & $venvPython @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller terminó con código $LASTEXITCODE" }
    if ($BuildMode -eq "onefile") {
        $builtExecutable = Join-Path $modePath "midi2it.exe"
    } else {
        $builtExecutable = Join-Path $modePath "midi2it\midi2it.exe"
    }
    if (-not (Test-Path $builtExecutable)) { throw "No se encontró el ejecutable: $builtExecutable" }
    Write-Host "Build listo: $builtExecutable" -ForegroundColor Green
}

if ($BuildOnly) {
    Write-Host "Build solicitado solamente; conversión omitida." -ForegroundColor Green
    exit 0
}

if ($launchGui) {
    if (-not $builtExecutable) {
        if ($BuildMode -eq "onefile") {
            $builtExecutable = Join-Path $repoRoot "dist\$BuildMode\midi2it.exe"
        } else {
            $builtExecutable = Join-Path $repoRoot "dist\$BuildMode\midi2it\midi2it.exe"
        }
    }
    if (Test-Path $builtExecutable) {
        Write-Host "Abriendo GUI: $builtExecutable" -ForegroundColor Cyan
        Start-Process -FilePath $builtExecutable -WorkingDirectory $repoRoot
    } else {
        Write-Host "Abriendo GUI desde Python (no hay build disponible)..." -ForegroundColor Yellow
        & $venvPython (Join-Path $repoRoot "midi2it.py") -g
    }
    exit 0
}

$midiFullPath = Resolve-RepoPath $MidiPath
if (-not (Test-Path $midiFullPath)) { throw "No se encontró el MIDI: $midiFullPath" }

$sf2FullPath = Resolve-RepoPath $Sf2Path
if (-not (Test-Path $sf2FullPath)) { throw "No se encontró el SF2: $sf2FullPath" }

$outputFullPath = Resolve-RepoPath $OutputPath
$outputDirectory = Split-Path -Parent $outputFullPath
if (-not (Test-Path $outputDirectory)) { New-Item -ItemType Directory -Path $outputDirectory | Out-Null }

Invoke-Conversion $venvPython $midiFullPath $sf2FullPath $outputFullPath

if ($builtExecutable) {
    $packagedOutput = [System.IO.Path]::ChangeExtension($outputFullPath, ".packaged.it")
    Invoke-Conversion $builtExecutable $midiFullPath $sf2FullPath $packagedOutput
}

$openmpt = Get-Command openmpt123 -ErrorAction SilentlyContinue
if ($openmpt) {
    Write-Host "`nValidando con openmpt123..." -ForegroundColor Cyan
    & $openmpt.Source --info $outputFullPath
    if ($LASTEXITCODE -ne 0) { throw "openmpt123 rechazó $outputFullPath" }
} else {
    Write-Host "openmpt123 no está instalado; se omite esa validación." -ForegroundColor Yellow
}

$smconv = Get-Command smconv -ErrorAction SilentlyContinue
if ($smconv) {
    Write-Host "`nValidando conversión SNES con smconv..." -ForegroundColor Cyan
    $soundbankBase = [System.IO.Path]::ChangeExtension($outputFullPath, $null)
    $smconvOutput = & $smconv.Source -s -o $soundbankBase -V -b 5 $outputFullPath 2>&1
    $smconvOutput | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0 -or ($smconvOutput -join "`n") -match "(?i)more than 8 channels|\berror:") {
        throw "smconv reportó errores al convertir el IT."
    }
} else {
    Write-Host "smconv no está instalado; se omite esa validación." -ForegroundColor Yellow
}

Write-Host "`nListo. IT generado: $outputFullPath" -ForegroundColor Green
