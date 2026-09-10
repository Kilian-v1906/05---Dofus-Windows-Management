# =============================================================================
# build.ps1 - Script de compilation et d'empaquetage de Dofus Organizer
# =============================================================================

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Compilation & Empaquetage : Dofus Organizer v1.0.0      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Résolution de l'environnement virtuel Python
$VENV_PYTHON = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$VENV_PYINSTALLER = Join-Path $PSScriptRoot ".venv\Scripts\pyinstaller.exe"

if (Test-Path $VENV_PYINSTALLER) {
    $PYINSTALLER = $VENV_PYINSTALLER
} else {
    $PYINSTALLER = "pyinstaller"
}

Write-Host "[1/4] Vérification de PyInstaller..." -ForegroundColor Yellow
try {
    & $PYINSTALLER --version | Out-Null
} catch {
    Write-Error "PyInstaller n'est pas disponible. Installez-le avec : pip install pyinstaller"
    exit 1
}

# 2. Nettoyage des répertoires de build précédents
Write-Host "[2/4] Nettoyage des dossiers build/ et dist/..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (-not (Test-Path "release")) { New-Item -ItemType Directory -Path "release" | Out-Null }

# 3. Compilation avec PyInstaller
Write-Host "[3/4] Compilation du .exe avec PyInstaller..." -ForegroundColor Yellow
& $PYINSTALLER --noconfirm --clean "DofusOrganizer.spec"

$EXE_PATH = Join-Path $PSScriptRoot "dist\DofusOrganizer\DofusOrganizer.exe"
if (-not (Test-Path $EXE_PATH)) {
    Write-Error "La compilation PyInstaller a échoué : DofusOrganizer.exe introuvable."
    exit 1
}

Write-Host " -> Exécutable généré avec succès dans : dist\DofusOrganizer\DofusOrganizer.exe" -ForegroundColor Green

# 4. Création de l'archive Portable .zip
Write-Host "[4/4] Création de l'archive Portable .zip..." -ForegroundColor Yellow
$PORTABLE_ZIP = Join-Path $PSScriptRoot "release\DofusOrganizer_Portable_v1.0.0.zip"
if (Test-Path $PORTABLE_ZIP) { Remove-Item -Force $PORTABLE_ZIP }
Compress-Archive -Path "dist\DofusOrganizer\*" -DestinationPath $PORTABLE_ZIP -Force
Write-Host " -> Version portable prête : $PORTABLE_ZIP" -ForegroundColor Green

# 5. Recherche du compilateur Inno Setup (ISCC) pour l'installeur Setup.exe
Write-Host "`nRecherche du compilateur Inno Setup (ISCC)..." -ForegroundColor Yellow
$ISCC_CANDIDATES = @(
    "iscc.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)

$ISCC_PATH = $null
foreach ($cand in $ISCC_CANDIDATES) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) {
        $ISCC_PATH = $cand
        break
    } elseif (Test-Path $cand) {
        $ISCC_PATH = $cand
        break
    }
}

if ($ISCC_PATH) {
    Write-Host " -> Inno Setup détecté ($ISCC_PATH). Génération de l'installeur Setup.exe..." -ForegroundColor Yellow
    & $ISCC_PATH "installer.iss"
    $SETUP_PATH = Join-Path $PSScriptRoot "release\DofusOrganizer_Setup_v1.0.0.exe"
    if (Test-Path $SETUP_PATH) {
        Write-Host " -> Installeur Windows généré avec succès : $SETUP_PATH" -ForegroundColor Green
    }
} else {
    Write-Host " -> Inno Setup n'est pas encore installé." -ForegroundColor Yellow
    Write-Host "    Pour générer automatiquement le fichier d'installation DofusOrganizer_Setup.exe :" -ForegroundColor White
    Write-Host "    Exécutez dans un terminal : winget install JRSoftware.InnoSetup" -ForegroundColor Cyan
    Write-Host "    Puis relancez build.ps1." -ForegroundColor White
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  BUILD TERMINÉ AVEC SUCCÈS !" -ForegroundColor Green
Write-Host "  Livrables disponibles dans les dossiers :" -ForegroundColor Green
Write-Host "  1. dist\DofusOrganizer\DofusOrganizer.exe (Lancement direct)" -ForegroundColor White
Write-Host "  2. release\DofusOrganizer_Portable_v1.0.0.zip (Archive portable)" -ForegroundColor White
if (Test-Path "release\DofusOrganizer_Setup_v1.0.0.exe") {
    Write-Host "  3. release\DofusOrganizer_Setup_v1.0.0.exe (Installeur Setup)" -ForegroundColor White
}
Write-Host "==========================================================" -ForegroundColor Green
