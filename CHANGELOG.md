# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado semántico.

## [Sin publicar]

## [0.15.0] - 2026-10-24

#### Español
- Detalle de un riven: la tabla de las más baratas ahora incluye tus órdenes visibles (aunque estés invisible, el caché sea viejo o sean más caras que las 7), marca con "Este" la que tenés abierta y no la vuelve a abrir al tocarla.
- Mercado: si la búsqueda llega al tope de ~500 de warframe.market, lo avisa (faltan las más caras).
- El precio acepta como mucho 6 dígitos al escribirlo.
- Estado: al ponerte En juego/Online por 30 min, 1 h o 2 h, el "hasta" mostraba la hora del estado anterior (hasta 4 h); ahora muestra la pedida.
- Ajuste automático de un riven: además de horas, el tiempo propio acepta minutos (ej. "30m"); sirve para probarlo sin esperar.
- Si cambiás tu estado con el detalle de un riven abierto, tu fila de la tabla se actualiza sola.
- Interno: los contratos propios y ajenos viven en un solo lugar (state.py); cambiar un precio, republicar, cerrar o crear actualiza de una vez la tabla, las alertas y el detalle.

#### English
- Riven detail: the cheapest-orders table now includes your visible orders (even when invisible, with a stale cache or pricier than the 7), tags the one you have open as "This one" and doesn't reopen it on click.
- Market: if the search hits warframe.market's ~500 cap it now says so (the pricier ones are missing).
- The price field takes at most 6 digits when typing.
- Status: setting In game/Online for 30 min, 1 h or 2 h showed the "until" time of the previous status (up to 4 h); it now shows the requested one.
- Auto price drop for a single riven: besides hours, its own time accepts minutes (e.g. "30m"); handy to test it without waiting.
- If you change your status while a riven detail is open, your row in the table updates by itself.
- Internal: own and other sellers' listings now live in one place (state.py); changing a price, republishing, closing or creating updates the table, alerts and detail view at once.

## [0.14.0] - 2026-10-24

#### Español
- Ventas anónimas: aviso explícito la primera vez que se abre la app (con opción de desactivar) y el texto de Ajustes aclara que viene activado por defecto.
- Mercado: la tabla de resultados se pagina (10 a 500 por página, 25 por defecto) y se puede cambiar el tamaño.
- Si te olvidaste de elegir el origen (lote del stock) al crear un riven, ahora lo podés elegir al editarlo: cuenta un riven del lote como abierto y su costo pasa a contar dentro del lote.
- Reportar con logs: el encabezado de salud de los bucles hacía que el total superara el límite del servidor y el envío fallaba con "No se pudo enviar"; ahora el recorte incluye el encabezado.

#### English
- Anonymous sales: explicit notice the first time the app opens (with an option to turn it off), and the Settings text now says it is on by default.
- Market: the results table is paginated (10 to 500 per page, 25 by default) with a page-size selector.
- If you forgot to pick the origin (stock lot) when creating a riven, you can now pick it when editing it: it counts one riven of the lot as opened and its cost is counted inside the lot.
- Report with logs: the loop-health header pushed the total over the server limit, so sending failed with "Could not send now"; the trim now includes the header.

## [0.13.13] - 2026-10-24

#### Español
- Corregido: después de editar un riven (que se republica con otro id) o de cerrarlo, la tabla de las más baratas seguía mostrando el contrato viejo con su precio anterior. Ahora se descarta y la tabla se vuelve a pedir.

#### English
- Fixed: after editing a riven (it is republished under a new id) or closing it, the cheapest-orders table kept showing the old listing at its previous price. It is now discarded and the table is fetched again.

## [0.13.12] - 2026-10-24

#### Español
- Corregido: cuando Cloudflare (el filtro anti-robots de warframe.market) bloquea tu conexión, la app lo dice y explica qué es y qué probar, en lugar de mostrar "token vencido" o "sin conexión".

#### English
- Fixed: when Cloudflare (warframe.market's anti-bot filter) blocks your connection, the app now says so and explains what it is and what to try, instead of showing "expired token" or "offline".

## [0.13.11] - 2026-10-23

#### Español
- Mejorado: los reportes con logs ahora incluyen la salud de los procesos de fondo (último ciclo correcto y último error de cada uno), para detectar si alguno se trabó.
- Corregido: abrir una segunda instancia de la app mientras ya hay una viva ya no se cuenta como un cierre inesperado en los reportes.
- Interno: se reordenó el código (los procesos de fondo y la copia en la nube salen de app.py) y cada proceso de fondo deja una línea de log por ciclo. No cambia lo que ves.

#### English
- Improved: reports with logs now include the health of the background processes (last good cycle and last error of each), to spot any that got stuck.
- Fixed: opening a second instance of the app while one is already running is no longer counted as an unexpected shutdown in reports.
- Internal: code was reorganized (background processes and the cloud copy moved out of app.py) and each background process now logs one line per cycle. Nothing changes in what you see.

## [0.13.10] - 2026-10-23

#### Español
- Corregido: al recuperar el borrador de un riven nuevo, el aviso quedaba detrás de la ventana y se abría solo la lista de armas tapando los stats. Ahora el aviso se ve arriba y el arma queda elegida sin desplegar la lista.

#### English
- Fixed: when restoring a new riven draft, the notice showed behind the window and the weapon list opened by itself, covering the stats. The notice now shows on top and the weapon stays selected without opening the list.

## [0.13.9] - 2026-10-23

#### Español
- Mejorado: si cerrás el editor de un riven nuevo sin querer (clic afuera, Esc o la X) y lo reabrís en menos de 10 segundos, se recupera lo que habías cargado y aparece un aviso. No se guarda en disco: al cerrar la app se pierde.

#### English
- Improved: if you close the new riven editor by accident (click outside, Esc or the X) and reopen it within 10 seconds, what you had entered is restored and a notice appears. It is not saved to disk: closing the app discards it.

## [0.13.8] - 2026-10-23

#### Español
- Corregido: la app no cargaba (Mis ventas quedaba en esqueletos, el estado en "Status..." y el selector de tipo vacío). La 0.13.7 traía un error de sintaxis en el código de la interfaz que impedía que arrancara; ahora está arreglado, y cada publicación revisa la sintaxis antes de salir.

#### English
- Fixed: the app would not load (My sales stuck on skeletons, status stuck on "Status..." and the type selector empty). 0.13.7 shipped a syntax error in the interface code that stopped it from starting; it is fixed, and every release now checks the syntax before publishing.

## [0.13.7] - 2026-10-23

#### Español
- Mejorado: el log ahora anota cuándo se abre y se cierra el editor de rivens y el panel de "¿Cuánto vale este riven?", para encontrar por qué ese panel desaparece al instante (reporte de Fran).

#### English
- Improved: the log now records when the riven editor and the "How much is this riven worth?" panel open and close, to find out why that panel vanishes instantly (reported by Fran).

## [0.13.6] - 2026-10-23

#### Español
- Mejorado: el log guarda cada pedido a warframe.market (cuándo salió, cuánto tardó, estado, headers de Cloudflare y el cuerpo si falló), cada llamada de la interfaz con su duración y errores, el entorno (sistema, proxies, reloj) y un diagnóstico de red automático ante 403, 429 o cortes. Ya no se pisa en cada arranque (rota en 3 archivos) y el reporte incluye las sesiones anteriores.
- Mejorado: la cola de pedidos a warframe.market registra en el log cada espera por 429 o corte de red, y si falla algo inesperado se recupera sola en vez de dejar la búsqueda cargando para siempre (reporte de Santino).
- Corregido: tras un ajuste automático de precio, el editor mostraba el precio viejo (ej. 20p en vez de 10p) porque Mis ventas no se actualizaba; ahora se refresca sola cuando llega una alerta.
- Nuevo: contador de slots de riven ("Slots 17/20") junto al estado y arriba de la tabla; el número de la izquierda son tus ventas publicadas (visibles u ocultas) y el de la derecha lo editás con un clic (también en Ajustes). Slots totales (15 base + packs de 5).

#### English
- Improved: the log now records every warframe.market request (when it left, how long it took, status, Cloudflare headers and the body on failure), every UI call with its duration and errors, the environment (system, proxies, clock) and an automatic network diagnostic on 403, 429 or drops. It is no longer overwritten on each start (it rotates over 3 files) and bug reports include previous sessions.
- Improved: the warframe.market request queue now logs every wait caused by a 429 or network drop, and recovers by itself from unexpected failures instead of leaving the search loading forever (reported by Santino).
- Fixed: after an automatic price drop, the editor showed the old price (e.g. 20p instead of 10p) because My sales was not refreshed; it now refreshes itself when an alert arrives.
- New: riven slot counter ("Slots 17/20") next to your status and above the table; the left number is your published listings (visible or hidden) and the right one is editable with a click (also in Settings). Total slots (15 base + packs of 5).

## [0.13.5] - 2026-10-23

#### Español
- Mejorado: el panel de Alertas tiene los botones del encabezado iguales (tamaño, color e íconos centrados), el tacho de cada alerta centrado y sin cambio de borde al pasar el mouse.
- Nuevo: botón para borrar una alerta individual, con animación, y "Borrar leídas" con confirmación.
- Mejorado: el panel abierto se actualiza solo con las alertas nuevas y mantiene un alto fijo.

#### English
- Improved: the Alerts panel now has uniform header buttons (size, color and centered icons), a centered trash button on each alert, and no border change on hover.
- New: button to delete a single alert, with animation, and "Delete read" with confirmation.
- Improved: the open panel updates itself with new alerts and keeps a fixed height.

## [0.13.4] - 2026-10-23

#### Español
- Mejorado: el estimado de precio ya no penaliza con un 0,6 fijo a los comparables con otra cantidad de stats. Ahora la penalización depende de la configuración (2 o 3 positivos, con o sin negativa) y sale de ventas reales: por ejemplo, 3 positivos sin negativa y 2 positivos con negativa se tratan casi como iguales.

#### English
- Improved: the price estimate no longer applies a flat 0.6 penalty to comparables with a different number of stats. The penalty now depends on the configuration (2 or 3 positives, with or without a negative) and is measured from real sales: for example, 3 positives with no negative and 2 positives with a negative are treated as nearly equal.

## [0.13.3] - 2026-10-23

#### Español
- Mejorado: la tabla de referencia ahora incluye también a los vendedores online (antes solo en juego) y muestra su estado.
- Corregido: tras cambiar el precio de un riven propio, la tabla de las más baratas seguía mostrando el precio viejo. Ahora se actualiza y tu orden lleva la etiqueta "Tu orden".
- Nuevo: en las tablas de comparables y de referencia al cargar un riven, cada vendedor lleva un punto de estado (en juego, online u offline) y una leyenda aclara que los offline pesan la mitad en el estimado.

#### English
- Improved: the reference table now also includes online sellers (previously in-game only) and shows their status.
- Fixed: after changing the price of one of your own rivens, the cheapest-orders table kept showing the old price. It now updates and your order carries a "Your order" tag.
- New: in the comparables and reference tables when loading a riven, each seller has a status dot (in game, online or offline) and a note explains that offline sellers weigh half in the estimate.

#### Español
- Mejorado: las alertas de baja agrupadas ahora muestran la última baja (cuánto bajó esa vez) y, aparte, el precio original («Original 150 pt»). El botón dice a qué precio revierte («Revertir a 130») y sigue deshaciendo solo la última baja.

#### English
- Improved: grouped drop alerts now show the latest drop (how much it dropped that time) and, separately, the original price ("Original 150 pt"). The button says which price it reverts to ("Revert to 130") and still undoes only the last drop.

## [0.13.2] - 2026-10-23

#### Español
- Corregido: al editar un riven (se publica uno nuevo y se cierra el viejo) se borraban el interruptor de ajuste automático y los ajustes propios de todos los demás rivens, y por eso bajaba precios con el interruptor apagado. Ahora no se toca a los demás.
- Corregido: al editar un riven, sus horas, interruptor, ajustes, historial de precios y alertas pasan a la publicación nueva. Antes la alerta quedaba apuntando al contrato viejo (abría un detalle sin engranaje y con el precio anterior).
- Las alertas de baja muestran el precio actual si lo cambiaste después, y ya no ofrecen revertir en ese caso.

#### English
- Fixed: editing a riven (a new listing is published and the old one closed) wiped the auto-drop switch and per-riven settings of every other riven, which made prices drop with the switch off. Other rivens are no longer touched.
- Fixed: when editing a riven, its hours, switch, settings, price history and alerts move to the new listing. Before, the alert kept pointing to the old contract (it opened a detail without the gear button and with the old price).
- Drop alerts show the current price if you changed it after the drop, and no longer offer to revert in that case.

## [0.13.1] - 2026-10-22
- Corregido: las etiquetas Caro/Barato y el botón «→ precio» ya no quedan desactualizadas después de cambiar el precio (aparecía «Barato → 70p» con el riven ya en 70p).

#### Español
- Corregido: al cambiar el precio de un riven (baja automática, manual o revertida) ahora también se actualiza el caché, así el detalle ya no muestra un precio distinto al del historial.
- Stock unveiled más compacto: los rivens sin abrir del mismo tipo y mismo costo unitario se agrupan en una sola fila, y al abrir uno elegís el grupo sin ver lotes repetidos.

#### English
- Fixed: the Expensive/Cheap tags and the "→ price" button no longer go stale after a price change (it showed "Cheap → 70p" with the riven already at 70p).
- Fixed: when a riven's price changes (automatic drop, manual or reverted) the cache is now updated too, so the detail no longer shows a price different from the history.
- More compact unveiled stock: unopened rivens of the same type and unit cost are grouped in a single row, and when opening one you pick the group without seeing repeated lots.

## [0.13.0] - 2026-10-22

#### Español
- Reemplazada la sección «Rentabilidad de rollear» del Reporte por «¿Conviene rolear?»: para cada riven publicado simula tiradas de Kuva y te dice si conviene rolearlo, cuántas veces, cuánto Kuva cuesta y la ganancia esperada. El valor del Kuva en platinum es ajustable.

#### English
- Replaced the "Rolling profitability" section of the Report with "Is it worth re-rolling?": for each listed riven it simulates Kuva rolls and tells you whether it pays off, how many rolls, the Kuva cost and the expected profit. The Kuva value in platinum is adjustable.

## [0.12.4] - 2026-10-22

#### Español
- Arreglado el scroll horizontal que aparecía en el diálogo de sugerencias y bugs; los botones Cancelar y Enviar ahora miden lo mismo.

#### English
- Fixed the horizontal scrollbar in the suggestions/bugs dialog; Cancel and Send buttons now have the same size.

## [0.12.3] - 2026-10-22

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
