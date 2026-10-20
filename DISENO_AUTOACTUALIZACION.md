# Diseño: autoactualización de Riven Stock (Épica 2)

Hoy la app se instala bajando el repo (ZIP o git clone) y ejecutando `instalar.bat`. Requiere Python en la PC. Los datos del usuario viven en `riven_stock.db`, `.env`/token y `cache/`, dentro de la carpeta de la app.

## Opciones

A. Updater basado en git (`git pull`)
- Pro: trivial de implementar.
- Contra: exige git instalado y que la carpeta sea un clon; los usuarios del ZIP quedan afuera; un pull falla si hay cambios locales.

B. GitHub Releases + updater que reemplaza archivos (recomendada ahora)
- Cada versión es un tag `vX.Y.Z` con un release; el asset es un zip del código de la app (sin db, .env, cache).
- Al iniciar (y cada tanto), la app consulta `https://api.github.com/repos/Franh01/riven-stock/releases/latest`, compara con `VERSION`, y si hay una nueva avisa con un aviso "Actualizar".
- Al aceptar: descarga el zip a una carpeta temporal, verifica el sha256 publicado en el release, un script auxiliar espera a que la app cierre, copia los archivos nuevos encima (preservando db, .env, cache, data), corre `pip install -r requirements.txt` si cambió, y relanza la app.
- Pro: sin empaquetado, sin antivirus molestando, funciona con ZIP o clon, release notes salen del mismo release (alimentan "Novedades").
- Contra: sigue necesitando Python en la PC.

C. Ejecutable (PyInstaller) + instalador (Inno Setup) + Releases
- Pro: experiencia tipo Discord, no requiere Python.
- Contra: falsos positivos de antivirus, builds más lentos y pesados, hay que firmar o convivir con SmartScreen, reemplazar el exe en uso es más delicado.
- Se puede sumar después sobre B sin cambiar el esquema de versiones ni de migraciones.

## Decisión propuesta
Hacer B primero, dejando la puerta abierta a C.

## Piezas
1. Archivo `VERSION` (semver) y constante leída por la app; se muestra en el panel de configuración.
2. `CHANGELOG.md` formato Keep a Changelog, pestaña "Novedades" en el panel; las notas del release de GitHub lo alimentan.
3. Chequeo de actualización: en segundo plano, al iniciar y cada 6 horas; tolerante a falta de red; nunca interrumpe mientras hay una baja automática en curso.
4. `updater.py` aparte, ejecutado como proceso independiente para poder reemplazar archivos de la app cerrada; con rollback si algo falla (carpeta `_backup_vX`).
5. Migraciones de la base: tabla `schema_version` y lista ordenada de migraciones en `store.py` que corren al abrir; backup automático de `riven_stock.db` antes de migrar.
6. Script `tools/release.py`: sube VERSION, arma el zip, calcula sha256, crea el tag y el release con `gh`.

## Riesgos
- Reemplazar archivos con la app abierta: se resuelve con el proceso updater separado.
- Una migración mala: backup previo de la base y rollback.
- Releases públicos: el repo no debe contener secretos (ya están en `.env`, ignorado).
