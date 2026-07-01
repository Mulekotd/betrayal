param(
    [string]$Python = "",
    [switch]$SkipInstall,
    [switch]$NoClean
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root
$ProjectRoot = [System.IO.Path]::GetFullPath($Root)

if (-not $Python) {
    $VenvPython = Join-Path $Root ".env\Scripts\python.exe"
    if (Test-Path $VenvPython) {
        $Python = $VenvPython
    } else {
        $Python = "python"
    }
}

if (-not $NoClean) {
    $BuildRoot = [System.IO.Path]::GetFullPath((Join-Path $Root "build"))

    if (-not $BuildRoot.StartsWith($ProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Build directory resolved outside the project root: $BuildRoot"
    }

    if (Test-Path $BuildRoot) {
        Remove-Item -LiteralPath $BuildRoot -Recurse -Force
    }
}

$BuildRoot = [System.IO.Path]::GetFullPath((Join-Path $Root "build"))
$StageRoot = Join-Path $BuildRoot "stage"
$StageApp = Join-Path $StageRoot "betrayal"

New-Item -ItemType Directory -Path $StageApp -Force | Out-Null

foreach ($Item in @("main.py", "src", "external", "pygbag.ini")) {
    $Source = Join-Path $ProjectRoot $Item
    Copy-Item -LiteralPath $Source -Destination $StageApp -Recurse -Force
}

if (-not $SkipInstall) {
    & $Python -m pip install -r build-requirements.txt
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

$IconPath = Join-Path $StageApp "src\assets\images\crown.png"

Push-Location $StageApp
try {
    & $Python -m pygbag `
        --build `
        --archive `
        --width 1280 `
        --height 720 `
        --title Betrayal `
        --app_name betrayal `
        --ume_block 1 `
        --icon $IconPath `
        .
} finally {
    Pop-Location
}

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$StageBuildRoot = Join-Path $StageApp "build"
$FinalWeb = Join-Path $BuildRoot "web"
$FinalCache = Join-Path $BuildRoot "web-cache"
$FinalZip = Join-Path $BuildRoot "web.zip"

foreach ($Path in @($FinalWeb, $FinalCache, $FinalZip)) {
    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

Copy-Item -LiteralPath (Join-Path $StageBuildRoot "web") -Destination $FinalWeb -Recurse -Force
Copy-Item -LiteralPath (Join-Path $StageBuildRoot "web.zip") -Destination $FinalZip -Force

$StageCache = Join-Path $StageBuildRoot "web-cache"
if (Test-Path $StageCache) {
    Copy-Item -LiteralPath $StageCache -Destination $FinalCache -Recurse -Force
}

Remove-Item -LiteralPath $StageRoot -Recurse -Force

Write-Host ""
Write-Host "Build web pronto em: build\web"
Write-Host "Arquivo para subir no itch.io: build\web.zip"
