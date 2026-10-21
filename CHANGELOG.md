# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado semántico.

## [Sin publicar]

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
