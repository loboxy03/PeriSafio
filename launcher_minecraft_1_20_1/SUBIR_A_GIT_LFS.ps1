param(
    [Parameter(Mandatory=$false)]
    [string]$SourceZip,
    [Parameter(Mandatory=$false)]
    [string]$RepoFolder = (Join-Path $env:USERPROFILE "PeriSafio-GitLFS")
)

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/loboxy03/PeriSafio.git"
$TempExtract = Join-Path $env:TEMP ("PeriSafio-LFS-" + [guid]::NewGuid().ToString("N"))

function Require-Command([string]$Name, [string]$InstallHint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name no está instalado o no está en PATH. $InstallHint"
    }
}

try {
    Require-Command "git" "Instala Git for Windows desde https://git-scm.com/download/win y vuelve a abrir PowerShell."
    if (-not $SourceZip) {
        $SourceZip = Read-Host "Ruta completa del ZIP de PeriSafio_Launcher_ACTUALIZAR_CORREGIDO.zip"
    }
    if (-not (Test-Path -LiteralPath $SourceZip -PathType Leaf)) {
        throw "No encuentro el ZIP: $SourceZip"
    }

    Write-Host "Comprobando Git LFS..." -ForegroundColor Cyan
    git lfs version
    if ($LASTEXITCODE -ne 0) {
        throw "Git LFS no está instalado. Instálalo desde https://git-lfs.com/ y vuelve a ejecutar."
    }

    New-Item -ItemType Directory -Path $TempExtract -Force | Out-Null
    Write-Host "Extrayendo archivos fuente..." -ForegroundColor Cyan
    Expand-Archive -LiteralPath $SourceZip -DestinationPath $TempExtract -Force
    $SourceRoot = Join-Path $TempExtract "launcher_minecraft_1_20_1"
    if (-not (Test-Path (Join-Path $SourceRoot "content\mods"))) {
        throw "El ZIP no tiene la estructura esperada launcher_minecraft_1_20_1\content\mods."
    }

    if (Test-Path (Join-Path $RepoFolder ".git")) {
        Write-Host "Usando repositorio local existente: $RepoFolder" -ForegroundColor Cyan
        git -C $RepoFolder fetch origin
        if ($LASTEXITCODE -ne 0) { throw "No se pudo hacer fetch del repositorio." }
        git -C $RepoFolder switch main
        if ($LASTEXITCODE -ne 0) { throw "No se pudo cambiar a la rama main." }
        git -C $RepoFolder pull --ff-only origin main
        if ($LASTEXITCODE -ne 0) { throw "No se pudo actualizar main; resuelve los cambios locales antes de continuar." }
    } else {
        if (Test-Path $RepoFolder) { throw "La carpeta destino ya existe y no es un clon Git: $RepoFolder" }
        Write-Host "Clonando $RepoUrl..." -ForegroundColor Cyan
        git clone $RepoUrl $RepoFolder
        if ($LASTEXITCODE -ne 0) { throw "Falló git clone. Comprueba Internet y permisos de GitHub." }
    }

    git -C $RepoFolder lfs install
    if ($LASTEXITCODE -ne 0) { throw "Falló git lfs install." }

    $TargetRoot = Join-Path $RepoFolder "launcher_minecraft_1_20_1"
    New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null
    foreach ($Folder in @("assets", "content")) {
        $From = Join-Path $SourceRoot $Folder
        $To = Join-Path $TargetRoot $Folder
        if (Test-Path $From) {
            if (Test-Path $To) { Remove-Item -LiteralPath $To -Recurse -Force }
            Copy-Item -LiteralPath $From -Destination $To -Recurse
        }
    }

    git -C $RepoFolder lfs track "*.jar" "*.zip" "*.jpg" "*.jpeg" "*.png" "*.ico" "*.mp3" "*.ogg" "*.wav"
    if ($LASTEXITCODE -ne 0) { throw "Falló la configuración de patrones LFS." }

    git -C $RepoFolder add .gitattributes launcher_minecraft_1_20_1/assets launcher_minecraft_1_20_1/content
    if ($LASTEXITCODE -ne 0) { throw "Falló git add." }

    Write-Host ""
    Write-Host "Archivos preparados. Revisa el resumen antes de subir:" -ForegroundColor Yellow
    git -C $RepoFolder status --short
    git -C $RepoFolder lfs status
    Write-Host ""
    $Confirm = Read-Host "¿Confirmas crear el commit y subir los binarios a GitHub LFS? (S/N)"
    if ($Confirm -notin @("S","s","SI","Si","si","Sí","sí")) {
        Write-Host "Cancelado. Los archivos quedaron preparados localmente en $RepoFolder." -ForegroundColor Yellow
        exit 0
    }

    git -C $RepoFolder commit -m "Add launcher assets, mods and resource packs via Git LFS"
    if ($LASTEXITCODE -ne 0) { throw "Falló el commit. Si dice que no hay cambios, revisa git status." }
    git -C $RepoFolder push origin main
    if ($LASTEXITCODE -ne 0) { throw "Falló el push. Revisa autenticación, cuota de Git LFS y límites de almacenamiento/transferencia de GitHub." }

    Write-Host ""
    Write-Host "Subida completada. Verifica los archivos en https://github.com/loboxy03/PeriSafio/tree/main/launcher_minecraft_1_20_1/content" -ForegroundColor Green
} catch {
    Write-Error $_
    exit 1
} finally {
    if (Test-Path $TempExtract) {
        Remove-Item -LiteralPath $TempExtract -Recurse -Force -ErrorAction SilentlyContinue
    }
}
