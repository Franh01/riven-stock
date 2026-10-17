# Riven Stock

App de escritorio para Windows que maneja tus rivens de Warframe y tus **ventas directas** en [warframe.market](https://warframe.market):

- **Mis ventas directas:** tus contratos (visibles y ocultos). Podés editar el precio, mostrar u ocultar, marcar como vendido o cerrar. Se ordenan por precio o por última actualización.
- **Precio de referencia:** las 7 ventas directas más baratas del arma, solo de vendedores que están **en el juego** ahora (los offline suelen ser publicaciones abandonadas).
- **Nuevo riven:** cargás el riven con autocompletado de armas y stats. El nombre sale solo, a partir de los stats. Mirás la referencia y lo publicás.
- **Costos y ganancias:** cuánto te costó cada riven, cuánto vendiste, cuánto invertiste y el balance.
- **Stock unveiled:** lotes de rivens sin abrir (por ejemplo, 6 melee por 50p). Al abrir uno, lo cargás con su costo ya puesto.

Los costos, el stock y el historial de vendidos quedan **solo en tu computadora** (en `riven_stock.db`). A warframe.market solo va lo que publicás, editás o cerrás.

> Solo ventas directas: las subastas se ignoran. Probado únicamente en **PC**.

## Requisitos

- Windows 10 u 11. Necesita WebView2, que ya viene con Windows 11 y con Edge.
- [Python](https://www.python.org/downloads/): probado con 3.14. Al instalarlo, marcá *"Add python.exe to PATH"*.
- Una cuenta de warframe.market.

## Instalación

1. Descargá el repo: en GitHub, **Code → Download ZIP**, y descomprimilo donde quieras tener la app. O con git: `git clone https://github.com/Franh01/riven-stock.git`.
2. Hacé **doble click en `instalar.bat`**. Se abre una terminal que:
   - busca Python,
   - instala lo que la app necesita,
   - te pide el **JWT** (ver abajo) y lo verifica con warframe.market, mostrándote con qué cuenta se conectó,
   - crea el acceso directo **Riven Stock** en el escritorio.

Si Windows muestra "Windows protegió su PC", tocá **Más información → Ejecutar de todas formas** (pasa con cualquier `.bat` descargado).

Para cambiar el token más adelante, por ejemplo cuando vence, volvé a ejecutar `instalar.bat`.

## El JWT: cómo conectar tu cuenta

La app usa tu **sesión de warframe.market**: no te pide email ni contraseña. Solo necesita el token de sesión (la cookie `JWT`), y con eso trabaja con **tu** cuenta.

1. Entrá a [warframe.market](https://warframe.market) e iniciá sesión.
2. Apretá **F12** → pestaña **Application** (o "Aplicación") → **Cookies** → `https://warframe.market`.
3. Buscá la cookie **`JWT`** y copiá su **Value** completo (es un texto largo que empieza con `eyJ`).
4. Pegalo cuando el instalador te lo pida. No se ve lo que pegás; es a propósito.

El instalador lo guarda en el archivo `.env` de la carpeta de la app. También podés editarlo a mano: `WFM_JWT=eyJ...`.

**Ojo con el token:**
- **Es como una contraseña.** Con él se puede publicar, editar y cerrar contratos en tu cuenta. No lo compartas ni lo subas a ningún lado; `.env` ya está excluido de git.
- **Dura unos 60 días.** Si la app empieza a dar error 401, copiá uno nuevo con los mismos pasos. Si cerrás sesión en la web, puede dejar de servir antes.

## Abrir la app

Con el acceso directo **Riven Stock** del escritorio. Si lo borraste, volvé a ejecutar `instalar.bat`, o desde la carpeta de la app:

```powershell
.venv\Scripts\pythonw.exe app.py
```

<details>
<summary>Instalación manual (sin instalar.bat)</summary>

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env      # y pegá el token en WFM_JWT=
powershell -ExecutionPolicy Bypass -File tools\create_shortcut.ps1
```
</details>

## Cosas a saber

- **Todo lo que hacés en "Mis ventas directas" es real en tu cuenta:** publicar, cambiar el precio, ocultar y cerrar. Publicar y cerrar piden confirmación.
- **Cerrar un contrato lo borra de warframe.market.** La app guarda una copia, con el precio de venta si lo marcaste como vendido, en "Cerrados desde la app".
- **Si ves un error 429**, warframe.market está limitando los pedidos. Esperá un minuto.
- **El nombre del riven** lo valida warframe.market, que lo rechaza si no corresponde a los stats. La app propone todas las combinaciones posibles y marca la más probable. Si dice **"revisá"**, compará con el nombre que ves en el juego.

## Para desarrollo

- `wfm_client.py`: todas las llamadas a la API de warframe.market.
- `app.py`: la ventana (pywebview) y la capa que usa la interfaz.
- `store.py`: la base local (SQLite).
- `ui/index.html`: la interfaz.
- `tools/derive_riven_bases.py`: regenera `data/riven_bases.json` (los valores base de los stats, sacados del export público de Digital Extremes) si el juego cambia los rivens.

La API de escritura de warframe.market no está documentada oficialmente y puede cambiar.
