# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado semántico.

## [Sin publicar]

#### Español
- El reporte de bugs y sugerencias ahora trae el log tildado por defecto y tiene un diseño más prolijo (selector de tipo y opciones agrupadas).

#### English
- The bug/suggestion dialog now has the log checked by default and a cleaner layout (type selector and grouped options).

## [0.12.2] - 2026-10-22

#### Español
- Los errores 401/403 de warframe.market ahora guardan en el log qué endpoint falló y qué respondió, y el mensaje ya no afirma que el token venció.

#### English
- warframe.market 401/403 errors now log which endpoint failed and what it replied, and the message no longer claims the token expired.

## [0.12.1] - 2026-10-22

#### Español
- Compartir ventas anónimas ahora viene activado por defecto (se puede apagar en Ajustes, Copia en la nube).

#### English
- Anonymous sales sharing is now on by default (you can turn it off in Settings, Cloud backup).

## [0.12.0] - 2026-10-22

#### Español
- Ajustes: nuevo interruptor opcional (apagado por defecto) para compartir tus ventas de forma anónima (arma, atributos, precios y fechas, sin usuario) y mejorar las estimaciones.

#### English
- Settings: new optional switch (off by default) to share your sales anonymously (weapon, stats, prices and dates, no username) to improve estimates.

## [0.11.0] - 2026-10-22

#### Español
- Mercado: nueva sección «Lo más movido (24 h)» con las armas más vendidas y las que más publicaciones nuevas tuvieron (datos de la nube). Tocar un arma la busca en el mercado.

#### English
- Market: new "Most active (24 h)" section with the best-selling weapons and the ones with the most new listings (cloud data). Tapping a weapon searches it on the market.

## [0.10.1] - 2026-10-22

#### Español
- Actualizador: si la descarga se corta o llega corrupta, reintenta una vez sola y, si vuelve a fallar, explica el motivo (descarga incompleta, red, antivirus o proxy) en vez de un error genérico.

#### English
- Market: new "Most active (24 h)" section with the best-selling weapons and the ones with the most new listings (cloud data). Tapping a weapon searches it on the market.
- Updater: if the download is cut off or arrives corrupted, it retries once and, if it fails again, explains why (incomplete download, network, antivirus or proxy) instead of a generic error.

## [0.10.0] - 2026-10-22

#### Español
- Reporte: el gráfico de ganancia por período ahora tiene eje vertical de platino, líneas guía, las barras apoyan sobre el eje, y al pasar el mouse la barra brilla y muestra la ganancia de ese período.
- Reporte: nuevos botones para exportar tus ventas (respeta los filtros del reporte) y tu stock con costos a CSV, y un resumen mensual imprimible (se abre en el navegador para imprimir o guardar como PDF).
- Estimador: los comparables con distinta cantidad de positivos que tu riven pesan bastante menos; la misma configuración va primero.

#### English
- Report: the profit-over-time chart now has a vertical platinum axis, guide lines, bars sit on the axis, and hovering a bar makes it glow and shows that period's profit.
- Report: new buttons to export your sales (honoring the report filters) and your stock with costs to CSV, plus a printable monthly summary (opens in the browser to print or save as PDF).
- Estimator: comparables with a different number of positives than your riven count for much less; the same configuration comes first.

## [0.9.1] - 2026-10-22

#### Español
- Mercado: trae hasta 500 publicaciones (antes cortaba en las 150 más baratas y ocultaba a los vendedores online más caros). Columna de fecha de publicación, y se puede ordenar por precio, estado del vendedor y fecha (clic en el encabezado). Ahora se listan todas las publicaciones del arma (antes solo vendedores en juego u online) y hay filtros sobre la tabla: estado del vendedor, precio máximo, rolls máximos y negativo.
- El estimador tiene en cuenta cuánto lleva publicado tu riven sin venderse, que los comparables más baratos y parecidos marcan el nivel, y que las publicaciones viejas pesan menos; las razones se ven en la tarjeta.
- El estimador ahora conoce cada arma (reparto de daño, tabla propia incluida en la app): un negativo sobre el daño principal baja el precio, uno sobre un daño que el arma no usa casi no molesta, y un positivo inútil vale menos. Las razones se ven en la tarjeta del estimado.
- El estimador compara los valores según la configuración del riven (2 o 3 positivos, con o sin negativo): el mismo porcentaje no vale igual en cada una, y un riven de 2 positivos ya no se compara como si fuera uno de 3.
- Cumple las reglas de warframe.market: la app se identifica con su propio User-Agent (RivenStock/versión y el repositorio) en lugar de hacerse pasar por un navegador, y el WebSocket ya no manda un origen falso.
- La carga de órdenes en segundo plano respeta mejor el límite de búsquedas de contratos: 6 s entre armas y, ante un error, espera creciente de 10 a 60 s (antes 60 s fijos).

#### English
- Market: up to 500 listings (it used to cut at the 150 cheapest, hiding pricier online sellers). Posted-date column, sortable by price, seller status and date (click the header). All listings for the weapon are shown (before, only in-game/online sellers) with table filters: seller status, max price, max rolls and negative.
- The estimator now considers how long your riven has been listed unsold, that the cheaper close comparables set the level, and that old listings weigh less; reasons show in the card.
- The estimator now knows each weapon (damage split, bundled table): a negative on the main damage lowers the price, one on a damage the weapon doesn't use barely matters, and a useless positive is worth less. Reasons show in the estimate card.
- The estimator compares values according to the riven's configuration (2 or 3 positives, with or without a negative): the same percentage isn't worth the same in each, and a 2-positive riven is no longer compared as if it were a 3-positive one.
- Follows the warframe.market rules: the app identifies itself with its own User-Agent (RivenStock/version plus the repository) instead of posing as a browser, and the WebSocket no longer sends a fake origin.
- Background order loading respects the contract-search limit better: 6 s between weapons and, on error, a growing wait of 10 to 60 s (it used to be a fixed 60 s).

## [0.9.0] - 2026-10-21

#### Español
- Nuevo en el Reporte: «Rentabilidad de rollear» (costo por riven vendible, porcentaje aprovechable, ganancia por tipo y armas que mejor se venden de tus lotes).
- Corregido: las etiquetas Caro/Barato/Estancado no aparecían porque el caché de órdenes no se completaba mientras usabas la app; ahora se carga en segundo plano al abrir Mis ventas.
- Corregido: el caché de órdenes ahora se guarda entre sesiones.
- La barra de «warframe.market pidió esperar» ahora avanza con la cuenta regresiva.
- Nuevo en Ajustes: «Ver pedidos a warframe.market» muestra arriba a la izquierda los últimos 3 pedidos con nombre corto.
- Corregido: «Ver publicación» en las alertas de oportunidad ahora abre el detalle del riven dentro de la app.

#### English
- New in Report: "Rolling profitability" (cost per sellable riven, usable share, profit by type and best-selling weapons from your lots).
- Fixed: the Expensive/Cheap/Stale tags were not showing because the order cache was not filled while you used the app; it now loads in the background when opening My sales.
- Fixed: the order cache is now saved between sessions.
- The "warframe.market asked to wait" bar now fills along with the countdown.
- New in Settings: "Show warframe.market requests" displays the last 3 requests top-left with short names.
- Fixed: "View listing" on opportunity alerts now opens the riven detail inside the app.

## [0.8.8] - 2026-10-21

#### Español
- Alertas de oportunidad: el selector no repite armas, muestra un contador (n/12) y se bloquea al llegar al tope; la ventana se ajusta a su contenido.
- Ajustes: copias locales y nube juntas bajo "Datos y respaldos", y General pasa a la columna izquierda.

#### English
- Opportunity alerts: the picker no longer repeats weapons, shows a counter (n/12) and locks at the limit; the window fits its content.
- Settings: local backups and cloud together under "Data and backups", with General moved to the left column.

## [0.8.7] - 2026-10-21

#### Español
- Tu stock se compara con el mercado: etiquetas Caro, Barato y Estancado en la tabla, filtro por etiqueta y un botón para ajustar el precio al estimado.
- Ajustes: el recorrido de respaldos ya no se desalinea cuando carga la información, títulos más claros (Respaldo de tus datos, Alertas de oportunidad) y las alertas de oportunidad tienen su propia ventana, con un botón de rayo en la cabecera; Ajustes ya no cambia de tamaño y los tags quedan centrados. En Ayuda, los recorridos pasan a un selector único.

#### English
- Your stock is compared against the market: Pricey, Cheap and Stale tags in the table, a tag filter and a button to set the price to the estimate.
- Settings: the backup tour no longer misaligns while data loads, clearer titles (Back up your data, Opportunity alerts) and opportunity alerts get their own window, opened by a lightning button in the header; Settings no longer resizes and tags are centered. In Help, tours now live in a single selector.

## [0.8.6] - 2026-10-21

#### Español
- El estimado ahora propone tres precios (rápido, estimado, alto) y muestra cuánto tardaron en venderse tus ventas anteriores, con un botón ? que explica cada precio.

#### English
- The estimate now suggests three prices (fast, estimate, high) and shows how long your previous sales took to sell, with a ? button explaining each price.

## [0.8.5] - 2026-10-21

#### Español
- El precio máximo al publicar o editar es 900000p: el campo lo limita y avisa.
- El error de datos inválidos de warframe.market ahora se explica en español.

#### English
- The maximum price when listing or editing is 900000p: the field caps it and warns.
- warframe.market's invalid-data error is now explained clearly.

## [0.8.4] - 2026-10-21

#### Español
- Al editar un riven, el estimado ya no cuenta tu propia publicación como comparable.
- La confirmación de edición muestra los stats antes y después, con el aviso de republicación arriba en naranja y botones simétricos.
- Los rechazos de warframe.market (ej. precio fuera de rango) se muestran en español indicando qué campo falló.

#### English
- When editing a riven, the estimate no longer counts your own listing as a comparable.
- The edit confirmation shows stats before and after, with the republish warning on top in orange and symmetric buttons.
- warframe.market rejections (e.g. out-of-range price) are shown clearly, naming the failing field.

## [0.8.3] - 2026-10-21

#### Español
- Corregido: el idioma elegido y las armas seguidas no se guardaban al reiniciar.
- El botón del estimado ahora es "¿Cuánto vale este riven?", el estimado muestra el rango del mod en los comparables y, si faltan stats, marca los campos y avisa.
- Nuevo riven: el origen vuelve arriba, MR, rango y rolls quedan a la vista, y el estimado con comparables también está al crear (usa los stats que cargaste).

#### English
- Fixed: the chosen language and tracked weapons were not saved across restarts.
- The estimate button is now "What's it worth?", comparables show the mod rank and, if stats are missing, the fields are highlighted with a warning.
- New riven: origin is back on top, MR, rank and rolls are visible again, and the comparables estimate is available when creating (uses the stats you entered).

## [0.8.2] - 2026-10-21

#### Español
- Arreglo: en algunas instalaciones la app no cargaba (pantalla en blanco) por un error en el lector de las notas de versión.

#### English
- Fix: on some installs the app did not load (blank screen) because of an error in the release notes reader.

#### Español
- El diálogo de "Nuevo riven" es más simple: origen, MR, rango y rolls quedan plegados en "Más detalles", y costo, visibilidad y nota en "Opciones" al publicar.

#### English
- The "New riven" dialog is simpler: origin, MR, rank and rolls are folded into "More details", and cost, visibility and note into "Options" when publishing.

## [0.8.1] - 2026-10-21

#### Español

### Agregado
- Recorrido guiado de las alertas de oportunidad (botón ? en la tarjeta y en la Ayuda), en español e inglés.
- Ajustes rediseñados: ventana más ancha en dos columnas ("Precios y alertas" y "General"), con iconos y una sección de datos y copias.
- "En juego al abrir la app" pasa a Ajustes como switch; "Invisible al cerrar" queda solo en Ajustes y se quita del menú de estado.
- Las armas vigiladas en Oportunidad se ven como etiquetas con botón para quitarlas.
- La ventana arranca maximizada.
- Las notas de versión ahora vienen en español e inglés; la app muestra la de tu idioma.

### Corregido
- Alertas de oportunidad: el estimado ya no sale tachado y los textos de cada fila quedan alineados al centro.
- El tooltip del engranaje decía "ajuste automático de precio"; ahora dice "Ajustes".
- Falso aviso de falla al abrir: las llamadas de la interfaz esperan a que la API de Python esté lista.

#### English

### Added
- Guided tour of the opportunity alerts (? button on the card and in Help), in Spanish and English.
- Release notes now come in Spanish and English; the app shows the one for your language.
- Redesigned Settings: wider window in two columns ("Prices and alerts" and "General"), with icons and a data and backups section.
- "In game when opening the app" moves to Settings as a switch; "Invisible when closing" stays only in Settings and is removed from the status menu.
- Watched weapons in Opportunity show as tags with a button to remove them.
- The window opens maximized.

### Fixed
- Opportunity alerts: the estimate is no longer struck through and the text in each row is centered.
- The gear tooltip said "automatic price adjustment"; it now says "Settings".
- False failure notice on startup: the interface waits for the Python API to be ready before calling it.

## [0.8.0] - 2026-10-21

#### Español

### Agregado
- Alertas de oportunidad: la app busca en segundo plano publicaciones muy por debajo del estimado (descuento y ganancia mínimos configurables, armas vigiladas a elección) y avisa con un botón a la publicación.

#### English

### Added
- Opportunity alerts: the app searches in the background for listings far below the estimate (configurable discount and minimum gain, weapons watched at your choice) and notifies you with a button to the listing.

## [0.7.0] - 2026-10-21
- Informes de errores: si la app se cierra con un error, al abrirla de nuevo te ofrece enviar un informe técnico (sin token ni datos personales); podés elegir enviarlos siempre.
- Si una versión nueva falla varias veces seguidas, te ofrece volver a la última que andaba bien.
- Seguridad: límites anti-abuso en la copia en la nube y dependencias actualizadas.

## [0.6.5] - 2026-10-21
- Nuevo botón de sugerencias y reporte de bugs en el encabezado: texto, hasta 3 capturas y, si querés, el registro de la app sin datos personales (con vista previa). Un envío cada 10 minutos.

## [0.6.4] - 2026-10-21

- Versión de prueba del actualizador de la app instalada (sin cambios visibles).

## [0.6.3] - 2026-10-21

- Corregido: actualizar desde la app instalada a veces no instalaba nada ni la reabría. Ahora un ayudante espera a que la app se cierre del todo, corre el instalador y la reabre si nadie lo hizo. Si tu versión es anterior a esta, reinstalá una vez con el Setup.exe nuevo.

## [0.6.2] - 2026-10-21

- El número de usuarios activos (últimos 30 días, conteo anónimo) ahora se ve junto al logo, con un indicador verde, sin abrir la configuración.

## [0.6.1] - 2026-10-21

- Reporte: mapa de calor de cuándo vendés (día de la semana y hora) con sugerencia de en qué franja conviene estar online, y tiempo hasta vender (mediana de horas online) por rango de precio y por arma, con sugerencia de tiempo para la baja automática. Las horas se registran desde esta versión.
- Corregido: en ventanas angostas el encabezado y los totales se salían de la pantalla; ahora se acomodan en una segunda línea.

## [0.6.0] - 2026-10-21

- Instalador para Windows (Setup.exe): se puede usar sin tener Python. Se instala por usuario, sin permisos de administrador, y se actualiza solo desde la app.
- Nuevo botón de la llave en la barra de arriba: pegás tu token de warframe.market (se comprueba y se guarda en tu PC) con un link al tutorial para sacarlo. Aparece solo si falta.
- Actualizador: si una actualización falla y vuelve atrás, también borra los archivos que la versión nueva había agregado.
- Los cuadros de texto largos (como el del token) ahora tienen el mismo estilo oscuro que el resto de la app, en lugar del fondo blanco del navegador.

## [0.5.0] - 2026-10-21

- Copias de seguridad: los datos pasan a la carpeta del usuario (%APPDATA%\RivenStock), así reinstalar no los borra (la base actual se copia sola la primera vez). Copia automática diaria y al cerrar, y en Configuración: copiar ahora, exportar, importar y abrir carpeta.
- Copia en la nube: opcional, cifrada en tu PC con un código de recuperación que solo vos tenés; se sube sola cada día y al cerrar, y se restaura en otra PC con el código. Muestra además cuántos usuarios activos hay (conteo anónimo).
- Reporte de ventas: nueva pestaña con ingresos, ganancia y margen, gráfico de ganancia en el tiempo y ranking de armas más rentables, con filtros por período, arma y tipo. Incluye recorrido guiado (botón ? y Ayuda; arranca solo la primera vez).

## [0.4.0] - 2026-10-21

- Tendencias en la nube: el historial de cada arma se lee de una base en la nube (foto diaria de todas las armas, armada por un colector programado en AWS). Sin conexión con la nube se usa la foto local de antes.

- Selectores: todos los desplegables tienen un estilo propio unificado (lista oscura con acento violeta, teclado y apertura hacia arriba si no hay lugar).

- Idioma: la app está en español e inglés (se elige en Configuración; por defecto el del sistema). Cambia en caliente, con ayuda, recorridos y mensajes de error traducidos.

## [0.3.4] - 2026-10-21

- Recorrido inicial: vuelve el paso «Editar uno publicado», ahora explicando que se pueden cambiar todos los datos y cómo lo resuelve la app (republica el contrato).

## [0.3.3] - 2026-10-21

- Editar un riven publicado ahora permite cambiar todos los datos (arma, nombre, stats, MR, rango, rolls y polaridad). Por detrás se republica el contrato y se cierra el anterior; el costo y el vínculo con el lote pasan al nuevo.

- Recorrido inicial: se quitó el paso «Editar uno publicado», que describía solo la edición de polaridad.

- Ayuda y recorrido: se explica en detalle cómo se cuentan las horas online de cada riven y su relación con el Ajuste automático de precio.

## [0.3.2] - 2026-10-21

- Los timeouts y cortes de red con warframe.market se reintentan solos (hasta 3 veces) antes de mostrar un error, con aviso del motivo; los errores ahora son mensajes claros, sin textos técnicos.

- Recorrido guiado de Stock unveiled (botón ? del panel o desde Ayuda) y entrada en la ayuda.
- Alineado el alto del botón «Agregar al stock» con los campos del formulario.

- Arreglo: «No volver a mostrar tutoriales» ahora se guarda y no reaparece al reabrir la app.

## [0.3.1] - 2026-10-21

- «Baja automática» pasa a llamarse «Ajuste automático de precio» en toda la app.
- Botón «Buscar actualizaciones» en Novedades.
- Ayuda: aclarado el botón Nuevo riven, el estado de warframe.market y el límite de pedidos.

## [0.3.0] - 2026-10-21
- Recorrido guiado inicial (se muestra solo la primera vez, se puede saltar o desactivar, y se repite desde Ayuda): crea un riven de ejemplo, recorre la lista, el menú de acciones, la edición, el estimado y el detalle con las migas de pan, todo con datos de ejemplo.
- Referencias y comparables plegados en 'Ver las N órdenes' para no saturar la edición.
- Campos numéricos sin las flechitas.
- Mercado: foto diaria por arma (cantidad, mínimo y mediana) de tus rivens en stock, tomada en idle por la cola central. Base para las tendencias.
- Resumen de un riven: tarjeta de tendencia del arma (mediana y mínimo de los últimos 90 días, con variación).
- Tendencia: estrella para seguir un arma aunque no la tengas en stock; se le saca una foto diaria igual.
- Pantalla de bienvenida breve mientras carga warframe.market, y botón "?" de ayuda con la explicación de las funciones.

## [0.2.5] - 2026-10-20

- Editar riven: el encabezado trae el switch de baja automática y sus ajustes (horas, baja, piso) de ese riven.
- Editar riven: botón Cancelar junto a Guardar; si venías del resumen, vuelve a él.
- Editar riven: una sola barra de scroll.
- Resumen de un riven propio: engranaje junto a los íconos para editarlo.
- Confirmación de guardar/publicar como modal, con filas de colores (viejo tachado en rojo, nuevo en verde, diferencia).
- Órdenes: estado y nombre del vendedor centrados.

## [0.2.4] - 2026-10-20

- Los avisos (toast) ahora se ven por encima de los diálogos abiertos.
- Resumen de un riven: botón con ícono de link que copia la URL de la publicación en warframe.market.
## [0.2.3] - 2026-10-20

- Editar: al tocar un precio sugerido (mínimo, mediana, promedio o estimado) la ventana baja con scroll suave hasta el campo Precio y lo hace parpadear.
## [0.2.2] - 2026-10-20

- Log de arranque en riven-stock.log (junto a app.py): registra errores de importación y de ejecución, que antes se perdían con pythonw, y muestra un aviso si la app no puede arrancar.
## [0.2.1] - 2026-10-20

- Editar un riven: botón "Calcular estimado con comparables" (avisa que puede tardar) que muestra el estimado, el rango y los comparables, y permite usar el estimado como precio.
## [0.2.0] - 2026-10-20

- Resumen: esqueleto con el mismo layout que el diálogo final, estimado de espera (n de total y segundos) desde la cola, expansión vertical animada al cargar y al navegar, y breadcrumbs destacados con botón Volver debajo del título.
- Los comparables del estimado también se abren con un clic (mismo comportamiento que las más baratas).
- Los comparables y las más baratas muestran hace cuánto se publicó cada riven, si el vendedor está en juego, online u offline y, si está offline, cuándo se conectó por última vez.
- Tabla "Más baratas" con el mismo estilo que los comparables (rolls y rango). Cada fila se abre como resumen propio, con migas de pan para volver atrás, y el cambio de pestaña anima el alto de la ventana en 160 ms.
- Comparables del estimado rediseñados: precio, rolls y rango juntos a la izquierda, stats en común con tu riven resaltados, barra de parecido y una leyenda que explica el orden.

- Estimador: los valores de los stats pesan más y se comparan a rango máximo (un riven sin subir ya no se confunde con uno maxeado). La tabla "Usadas para el estimado" ahora muestra rolls y rango de cada comparable.

- Cola central de pedidos a warframe.market: nunca más de 3 por segundo, en orden de llegada (FIFO), y si la API pide esperar (429) se frena todo y se reintenta sin perder el turno. Barra de progreso con porcentaje y tiempo estimado cuando hay varios pedidos en espera.

- Pestaña Mercado: buscá rivens de cualquier arma (con hasta 3 stats positivos) y tocá uno para ver su precio estimado, los comparables y si está barato.
- Resumen: tocar el nombre abre la edición del contrato.
- Estimado: si warframe.market limita los pedidos y faltan comparables, lo avisa en vez de mostrar un número bajo sin explicación.

## [0.1.8] - 2026-10-20

- Precio estimado: los pesos de cada stat dependen del tipo de arma (rifle, escopeta, pistola, melee, kitgun, zaw).
- Pantallas de carga con skeletons animados (lista de ventas, resumen, ajustes y referencia de precios).

## [0.1.7] - 2026-10-20

- Precio estimado: ahora consulta al mercado por la combinación exacta de stats positivos (y por pares), no solo las más baratas del arma.
- Precio estimado: la similitud prioriza cubrir tus stats positivos y pondera más fuerte a los más parecidos.

## [0.1.6] - 2026-10-20

### Agregado
- Precio estimado en el resumen de cada riven: compara con publicaciones del mismo arma con stats parecidos (no solo las más baratas) y muestra estimado, rango, confianza y comparables.

## [0.1.5] - 2026-10-20

### Cambiado
- La app busca actualizaciones cada 1 hora, no solo al abrir.
- Los modales se cierran al hacer click fuera de ellos.

## [0.1.4] - 2026-10-20

### Cambiado
- Al abrir un riven, las órdenes se vuelven a pedir si los datos tienen más de 10 minutos.
- Botón de cerrar de los modales más grande y sin recuadro de foco al abrir.

## [0.1.3] - 2026-10-20

### Cambiado
- El aviso de versión nueva aparece solo al abrir la app, en un modal con las novedades y el botón Actualizar a la derecha.
- Novedades ordenadas por versión, sin texto de relleno.
- Al actualizar se muestra un aviso de que la app se reinicia.

## [0.1.2] - 2026-10-20

### Cambiado
- Versión de prueba del flujo de actualización automática.

## [0.1.1] - 2026-10-20

### Corregido
- La interfaz no cargaba en 0.1.0 (quedaba en "Cargando...").

## [0.1.0] - 2026-10-20
### Agregado
- Baja automática de precio de tus rivens, con horas en línea, monto y piso mínimo, global y por riven.
- Alertas con sonido, agrupadas por riven, con "Ver Riven" y "Revertir".
- Estado Invisible sin opciones de tiempo.
- Retención automática del historial de alertas.
- Autoactualización desde GitHub Releases y pestaña de novedades.

## [0.0.0] - 2026-10-01
### Agregado
- Versión inicial sin número (instalación por ZIP o git clone).
