# Instalador de Riven Stock. Se usa con doble click en instalar.bat.
#
# 1. Busca Python (3.10 o más nuevo).
# 2. Crea el entorno (.venv) e instala las dependencias.
# 3. Pide el JWT de warframe.market, lo verifica y lo guarda en .env.
# 4. Crea el acceso directo en el escritorio.
#
# Opcional: -ShortcutDir "C:\carpeta" crea el acceso directo en otra carpeta.
# Si la variable de entorno WFM_JWT ya tiene un token, se usa ese en vez de pedirlo.
# Compatible con Windows PowerShell 5.1 (el que trae Windows).
param(
    [string]$ShortcutDir = [Environment]::GetFolderPath('Desktop')
)

# Continue: con Stop, PowerShell 5.1 toma como error cualquier salida de pip/python por stderr.
# Los errores se detectan con $LASTEXITCODE.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Step($text) { Write-Host ""; Write-Host "==> $text" -ForegroundColor Magenta }
function Fail($text) {
    Write-Host ""
    Write-Host "ERROR: $text" -ForegroundColor Red
    exit 1
}

Write-Host "Riven Stock - instalador" -ForegroundColor Magenta
Write-Host "Carpeta: $root"

# ---- 1. Python ------------------------------------------------------------
Step "Buscando Python"
$python = $null
foreach ($candidate in @(@('py', '-3'), @('python'))) {
    try {
        $exe = $candidate[0]
        $extra = @($candidate | Select-Object -Skip 1)
        $version = & $exe @extra -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $version -match '^\d+\.\d+$') {
            $parts = $version.Split('.')
            if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 10) {
                $python = $candidate
                Write-Host "Python $version encontrado ($exe)."
                break
            }
        }
    } catch { }
}
if (-not $python) {
    Fail ("No encontré Python 3.10 o más nuevo.`n" +
          "Instalalo desde https://www.python.org/downloads/ y marcá 'Add python.exe to PATH'.`n" +
          "Después volvé a ejecutar instalar.bat.")
}

# ---- 2. Entorno y dependencias ----------------------------------------------
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    Step "El entorno (.venv) ya existe"
} else {
    Step "Creando el entorno (.venv)"
    $exe = $python[0]
    $extra = @($python | Select-Object -Skip 1)
    & $exe @extra -m venv .venv
    if ($LASTEXITCODE -ne 0) { Fail "No se pudo crear el entorno." }
}

Step "Instalando dependencias (puede tardar un minuto)"
& $venvPython -m pip install --disable-pip-version-check -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { Fail "Falló la instalación de dependencias (pip)." }
Write-Host "Listo."

# ---- 3. JWT -----------------------------------------------------------------
Step "Conectar tu cuenta de warframe.market"
$envFile = Join-Path $root ".env"
$existing = $null
if (Test-Path $envFile) {
    $line = Get-Content $envFile | Where-Object { $_ -match '^\s*WFM_JWT\s*=\s*\S+' } | Select-Object -First 1
    if ($line) { $existing = ($line -replace '^\s*WFM_JWT\s*=\s*', '').Trim() }
}

function Test-Token($token) {
    # El token va por variable de entorno (no por argumentos, que se ven en la lista de procesos).
    $env:WFM_JWT = $token
    try {
        $out = & $venvPython (Join-Path $root "tools\check_jwt.py") 2>&1
        return @{ Ok = ($LASTEXITCODE -eq 0); Message = ($out -join " ") }
    } finally {
        Remove-Item Env:WFM_JWT -ErrorAction SilentlyContinue
    }
}

$token = $null
$preset = $env:WFM_JWT
if ($preset) {
    $check = Test-Token $preset
    if ($check.Ok) { $token = $preset; Write-Host "Usando el token de la variable WFM_JWT: cuenta $($check.Message)." -ForegroundColor Green }
    else { Write-Host "El token de la variable WFM_JWT no sirve: $($check.Message)" -ForegroundColor Yellow }
}
if (-not $token -and $existing) {
    $check = Test-Token $existing
    if ($check.Ok) {
        Write-Host "Ya hay un token guardado y funciona: cuenta $($check.Message)." -ForegroundColor Green
        $answer = Read-Host "¿Querés reemplazarlo por otro? (s/N)"
        if ($answer -notmatch '^[sSyY]') { $token = $existing }
    } else {
        Write-Host "El token guardado ya no sirve: $($check.Message)" -ForegroundColor Yellow
    }
}

if (-not $token) {
    Write-Host ""
    Write-Host "La app necesita tu token de sesión (la cookie JWT). No pide email ni contraseña."
    Write-Host "  1. Entrá a https://warframe.market e iniciá sesión."
    Write-Host "  2. Apretá F12 -> pestaña Application (o 'Aplicación') -> Cookies -> https://warframe.market"
    Write-Host "  3. Copiá el valor (Value) completo de la cookie JWT. Empieza con 'eyJ'."
    Write-Host ""
    Write-Host "El token es como una contraseña: no lo compartas. Se guarda solo en el archivo .env de esta carpeta." -ForegroundColor Yellow
    for ($try = 1; $try -le 3 -and -not $token; $try++) {
        Write-Host ""
        $secure = Read-Host "Pegá el JWT (no se va a ver lo que pegás) y apretá Enter" -AsSecureString
        $plain = [System.Net.NetworkCredential]::new('', $secure).Password.Trim()
        if ($plain -match '^(?i)JWT=') { $plain = $plain.Substring(4).Trim() }  # por si copiaron "JWT=..."
        if (-not $plain) { Write-Host "No pegaste nada." -ForegroundColor Yellow; continue }
        if ($plain.Split('.').Count -ne 3) {
            Write-Host "Eso no parece un JWT (tiene que tener tres partes separadas por puntos). Probá de nuevo." -ForegroundColor Yellow
            continue
        }
        Write-Host "Verificando con warframe.market..."
        $check = Test-Token $plain
        if ($check.Ok) {
            $token = $plain
            Write-Host "Conectado como $($check.Message)." -ForegroundColor Green
        } else {
            Write-Host $check.Message -ForegroundColor Yellow
        }
    }
    if (-not $token) { Fail "No se pudo verificar el token. Volvé a ejecutar instalar.bat cuando tengas uno nuevo." }
}

# .env sin BOM (python-dotenv lo lee bien así).
[System.IO.File]::WriteAllText($envFile, "WFM_JWT=$token`r`n", (New-Object System.Text.UTF8Encoding $false))
Write-Host "Token guardado en .env"

# ---- 4. Acceso directo ----------------------------------------------------------
Step "Creando el acceso directo"
& (Join-Path $PSScriptRoot "create_shortcut.ps1") -Destination $ShortcutDir
if (-not $?) { Fail "No se pudo crear el acceso directo." }

Write-Host ""
Write-Host "Instalación terminada." -ForegroundColor Green
Write-Host "Abrí la app con el acceso directo 'Riven Stock' del escritorio."
$open = Read-Host "¿La abro ahora? (S/n)"
if ($open -notmatch '^[nN]') {
    Start-Process -FilePath (Join-Path $root ".venv\Scripts\pythonw.exe") -ArgumentList "`"$(Join-Path $root 'app.py')`"" -WorkingDirectory $root
}
