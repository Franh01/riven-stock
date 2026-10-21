# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado semántico.

## [Sin publicar]

## [0.8.0] - 2026-10-21

### Agregado
- Alertas de oportunidad: la app busca en segundo plano publicaciones muy por debajo del estimado (descuento y ganancia mínimos configurables, armas vigiladas a elección) y avisa con un botón a la publicación.

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
