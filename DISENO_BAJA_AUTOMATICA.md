# Diseño: baja automática de precio por horas online efectivas

Estado: v2, con los comentarios de Fran incorporados (2026-10-19). Épica 1. Pendiente de aprobación final.

## Reglas acordadas

- Se cuentan horas online efectivas, no días calendario. El contador es local.
- Si un riven lleva N horas efectivas publicado sin venderse, se le baja X platinos.
  Defaults: N = 10 h, X = 5 pt. Ambos configurables.
- La baja es automática, sin pedir confirmación. Interruptor general on/off (`autodrop_enabled`).
- Antes de bajar se valida que el precio propio no sea ya el más barato entre las
  órdenes ONLINE (estado `ingame` u `online`, nunca offline). Si ya lo es, no se baja.
- Cada baja genera un aviso persistente dentro de la app, en un panel de avisos, con botón para revertir.
- Solo corre con la app abierta. No hay servicio en segundo plano.
- Los rivens ya publicados antes de activar la función empiezan a contar desde cero.
- Al cerrar la app, el usuario pasa a invisible automáticamente. Configurable con check on/off (`invisible_on_close`).

## Cómo funciona el estado en warframe.market (hallazgos del código)

- El estado va por WebSocket (`wfm_client._ws_session`): se abre, se manda el comando
  y se cierra. El servidor lo mantiene hasta `statusUntil`, con máximo de 4 h.
- Hoy, al abrir la app se pone `ingame` por 4 h. Al cerrar no se cambia nada, así que
  el estado sigue vivo hasta que se agota.
- Bug conocido: la interfaz no muestra la hora de vencimiento al abrir. Sospecha:
  `set_status` devuelve `statusUntil: None` si el evento no llega a tiempo, y
  `changeStatus` en `ui/index.html` pisa con eso la hora optimista.

## Contador de horas online efectivas

- Una hora cuenta si el estado es `online` o `ingame` y la app está abierta.
- Un hilo de fondo toma una muestra cada minuto y suma el tiempo transcurrido, con
  tope por muestra para no contar suspensiones de la PC.
- Como el estado dura 4 h, la app lo renueva antes de que venza mientras esté abierta.
- Al cerrar la app: `set_status("invisible")`. Si el cierre es abrupto, el estado
  vence solo; el contador no suma porque la app no estaba abierta.

## Datos nuevos (SQLite local)

- `online_hours_log`: UNA sola fila con el acumulado total de horas efectivas. Nunca una fila por muestra.
- `riven_online_hours`: `auction_id`, `hours` acumuladas desde la publicación o desde
  la última baja, `counting_since`.
- `price_drops`: `id`, `auction_id`, `old_price`, `new_price`, `at`, `reverted_at`.
  Permite el historial y la reversión.
- En `settings`: `autodrop_enabled`, `autodrop_hours` (10), `autodrop_amount` (5),
  `autodrop_floor` (piso global, default 10 pt), `invisible_on_close`.
- Por riven (columnas en `riven_online_hours`): `autodrop_on` (switch propio, default
  encendido), `hours_override`, `amount_override`, `floor_override` (nulos = usa el global).
- `notifications`: `id`, `kind`, `auction_id`, `drop_id`, `text`, `created_at`, `read_at`.
  Alimenta el panel de avisos.

### Escalabilidad

- Volumen: `riven_online_hours` tiene una fila por riven publicado (decenas o cientos) y
  se actualiza en el lugar. `online_hours_log` es una fila. Ninguna crece con el tiempo.
- Lo único que crece es `price_drops` y `notifications`. Con N = 10 h, un riven baja como
  máximo ~2 veces por día de uso. Con 100 rivens son ~200 filas por día, ~70 mil al año:
  trivial para SQLite. Igual se pone retención: borrar avisos leídos de más de 60 días y
  bajas de más de 12 meses ya revertidas o sin riven vivo.
- Escrituras: el muestreo cada minuto solo hace un `UPDATE` de una transacción corta
  (suma de horas a todos los rivens en una sola sentencia). Se activa `WAL` y
  `busy_timeout` para que la UI nunca espere por el hilo de fondo.
- Índices: `price_drops(auction_id, at)` y `notifications(read_at, created_at)`.
- El cuello de botella real es la red, no la base: cada pasada hace una búsqueda
  `search_direct` por arma distinta. Se agrupa por arma (varios rivens del mismo arma
  comparten una consulta), se cachea el resultado unos minutos y se respeta `_throttle`.
  El modal de órdenes online reutiliza esa caché.

## Motor de baja

Cada pasada (por ejemplo cada 5 minutos, con la app abierta y estado online):

1. Sumar horas efectivas a cada riven publicado y visible.
2. Para cada riven con horas >= N y no excluido:
   a. Buscar las ventas directas del arma con `search_direct` y filtrar vendedores
   online (reutilizando `cheapest_ingame`, ampliado a `online`).
   b. Si el precio propio ya es el más bajo entre los online: no bajar y reiniciar el
   conteo del riven (esperar otras N horas).
   c. Si precio - X queda bajo el piso efectivo, bajar solo hasta el piso (o no bajar si
   ya está en el piso).
   d. Si no: `update_auction` con precio - X, registrar en `price_drops`, reiniciar
   las horas del riven y disparar la alerta.
3. Respetar el límite de pedidos (`_throttle`, 429) y no bajar más de un paso por pasada.

## Aviso con reversión

- Panel de avisos dentro de la app (persistente, con contador de no leídos). Cada aviso
  dice "Bajé X de A a B pt" y tiene dos acciones distintas:
  - Clic en el aviso: abre un modal con la publicación: el riven con sus stats, el precio
    actual y las 7 órdenes online más baratas de esa arma, de menor a mayor.
  - Botón "Revertir": un solo clic, pero con confirmación "¿Seguro? Sí / No".
- Revertir: `update_auction` al `old_price`, marcar `reverted_at`, y apagar el
  switch `autodrop_on` de ese riven para que no vuelva a bajar enseguida.
- Diseño del switch por riven: columna con interruptor en la tabla de rivens. El estado
  efectivo es: general ON y switch del riven ON. Si el general está OFF, los switches
  se ven deshabilitados pero conservan su valor. Revertir apaga solo el del riven, con
  un aviso que lo dice y permite reactivarlo ahí mismo. Apagar un riven no borra sus
  horas acumuladas; reactivarlo continúa desde donde estaba.

## Panel de configuración

- Activar/desactivar la baja automática.
- Cada cuántas horas efectivas (slider) y cuánto baja cada vez (slider o número).
- Mostrar el total de horas online acumuladas.
- Las horas por riven se ven como columna en la tabla, no en la configuración.
- Piso mínimo global y check de invisible al cerrar.
- Por riven: switch on/off, horas, monto y piso propios.

## Puntos abiertos

- Si el riven ya es el más barato al cumplirse las N horas, ¿reiniciar el conteo o
  volver a chequear en cada pasada? Propuesta: volver a chequear en cada pasada, sin
  reiniciar. DECIDIDO por Fran: reiniciar el conteo. Si ya es el más barato al cumplirse
  las N horas, las horas del riven vuelven a cero y esperan otras N.
- Piso mínimo: la regla de "ya es el más barato" lo cubre, pero se podría sumar un
  piso opcional (por ejemplo el costo del lote). DECIDIDO por Fran: sí, configurable global
  y por riven, con default 10 pt. Nunca se baja por debajo del piso efectivo.

## Orden de implementación

1. Contador de horas online + invisible al cerrar + arreglo del bug del tiempo.
2. Horas por riven e historial de precios.
3. Motor de baja con la validación.
4. Alerta con reversión.
5. Panel de configuración.
6. Prueba con datos reales (umbral bajo para testear).
