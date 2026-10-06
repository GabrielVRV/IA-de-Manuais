<#
.SYNOPSIS
    Gera o build do frontend e publica na pasta do XAMPP.

.DESCRIPTION
    - Substitui index.html, assets/ e demais arquivos estaticos.
    - PRESERVA o config.json ja existente no destino (ele aponta para a API do servidor).
    - Use sempre uma pasta exclusiva da aplicacao, nunca a raiz do htdocs.

.EXAMPLE
    .\scripts\deploy-xampp.ps1 -Destino "C:\xampp\htdocs\ia-manuais"

.EXAMPLE
    .\scripts\deploy-xampp.ps1 -Destino "\\servidor\c$\xampp\htdocs\ia-manuais" -PularBuild
#>
param(
    [Parameter(Mandatory = $true)]
    [string] $Destino,

    [switch] $PularBuild
)

$ErrorActionPreference = 'Stop'

$raiz = Split-Path $PSScriptRoot -Parent
$dist = Join-Path $raiz 'dist'

if ((Split-Path $Destino -Leaf) -ieq 'htdocs') {
    throw "Destino '$Destino' e a raiz do htdocs. Use uma subpasta exclusiva, ex.: htdocs\ia-manuais"
}

if (-not $PularBuild) {
    Write-Host '==> Gerando build de producao...'
    Push-Location $raiz
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Falha no build.' }
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path (Join-Path $dist 'index.html'))) {
    throw "Build nao encontrado em '$dist'. Rode sem -PularBuild."
}

New-Item -ItemType Directory -Force -Path $Destino | Out-Null

# Remove os assets antigos: cada build gera arquivos com hash novo no nome.
$assetsDestino = Join-Path $Destino 'assets'
if (Test-Path $assetsDestino) { Remove-Item $assetsDestino -Recurse -Force }

$configDestinoExiste = Test-Path (Join-Path $Destino 'config.json')

Get-ChildItem $dist -Force |
    Where-Object { -not ($_.Name -eq 'config.json' -and $configDestinoExiste) } |
    Copy-Item -Destination $Destino -Recurse -Force

Write-Host "==> Publicado em $Destino"
if ($configDestinoExiste) {
    Write-Host '    config.json do servidor preservado.'
}
else {
    Write-Host '    ATENCAO: config.json criado com o valor padrao (localhost).' -ForegroundColor Yellow
    Write-Host '    Edite-o para apontar para a API do servidor, ex.: http://servidor:8000' -ForegroundColor Yellow
}
