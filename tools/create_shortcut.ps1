# Crea un acceso directo "Riven Stock" que abre la app sin consola.
#   powershell -ExecutionPolicy Bypass -File tools\create_shortcut.ps1
#   powershell -ExecutionPolicy Bypass -File tools\create_shortcut.ps1 -Destination "C:\otra\carpeta"
param(
    [string]$Destination = [Environment]::GetFolderPath('Desktop')
)

$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    Write-Error "No encuentro $pythonw. Primero creá el entorno: python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
    exit 1
}

$lnk = Join-Path $Destination "Riven Stock.lnk"
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = "`"$(Join-Path $root 'app.py')`""
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation = "$(Join-Path $root 'assets\icon.ico'),0"
$shortcut.Description = "Riven Stock - ventas directas de rivens en warframe.market"
$shortcut.Save()
Write-Output "Acceso directo creado: $lnk"
