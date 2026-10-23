# Riven Stock: arquitectura y flujos

Documento vivo. Se revisa en cada release (ver "Cómo mantenerlo" al final). Última revisión: 2026-10-23, sobre la versión 0.13.10.

Los diagramas son Mermaid: se ven en GitHub y en el visor de markdown del chat.

## 1. Componentes

```mermaid
flowchart LR
    subgraph PC["PC del usuario"]
        UI["ui/index.html<br/>lang_es.js / lang_en.js"] -- "pywebview js_api" --> API["app.py · class Api"]
        API --> STORE["store.py<br/>SQLite riven_stock.db"]
        API --> CACHE["orders.OrderCache<br/>cache/order_cache.json"]
        API --> RL["ratelimit.QUEUE<br/>cola FIFO, 3 req/s"]
        CACHE --> RL
        RL --> WFM["wfm_client.py"]
        API --> PRICING["pricing.py · stockcheck.py<br/>reroll.py · opportunities.py"]
        API --> UPD["updater.py"]
        API --> CRASH["crashes.py · feedback.py<br/>netdiag.py"]
        API --> CB["cloud_backup.py<br/>AES-GCM"]
    end
    WFM -- "REST + WebSocket" --> WM[("warframe.market")]
    UPD -- "Releases" --> GH[("GitHub")]
    CB --> LAM
    CRASH --> LAM
    subgraph AWS["AWS us-east-1 (cloud/)"]
        LAM["Lambdas: api · backup<br/>feedback · collector"] --> MONGO[("MongoDB Atlas M0")]
        LAM --> S3[("S3 feedback")]
        EB["EventBridge<br/>0/6/12/18 h"] --> LAM
    end
    LAM -- "collector" --> WM
```

Reglas que sostienen todo:
- Todo pedido a warframe.market pasa por `ratelimit.QUEUE` (un pedido en vuelo, ventana de 3 por 1,1 s, espera global ante 429).
- La UI nunca habla con la red: solo con `Api`. Las preferencias van a la tabla `settings` (pywebview corre en modo privado, no hay `localStorage`).
- Los datos personales (costos, lotes, horas, historial) son solo locales. A la nube va únicamente lo que el usuario activa: copia cifrada con su código, ping anónimo, ventas anónimas (opt-in).

## 2. Arranque y cierre

```mermaid
sequenceDiagram
    participant M as main()
    participant A as Api
    participant W as ventana pywebview
    M->>M: AppUserModelID, netdiag.environment/probe
    M->>A: Api() y start_counter()
    A->>A: lanza hilos (sección 3)
    M->>W: create_window(ui/index.html)
    W-->>A: evento shown (estado En juego por 4 h si auto_ingame)
    Note over W,A: ... uso normal ...
    W->>A: on_closing (se cancela el cierre)
    A->>W: showClosing
    A->>A: estado invisible (si invisible_on_close)
    A->>A: backup local (-cierre) y subida a la nube
    A->>A: crashes.end() y window.destroy()
```

## 3. Bucles de fondo

Todos arrancan en `start_counter`. Los de red no hacen pedidos propios fuera de la cola.

```mermaid
flowchart TB
    subgraph T["Hilos en app.py"]
        C["_counter_loop · TICK<br/>horas online y por riven (solo visibles)<br/>renueva el estado antes de las 4 h"]
        D["_drop_loop · 300 s<br/>autodrop_pass: baja como máximo UN riven"]
        S["_snapshot_loop · 120 s<br/>una foto por arma y día, solo en reposo"]
        O["_opp_loop · 90 s<br/>busca oportunidades en el caché, sin pedidos"]
        K["_cloud_loop · 1800 s<br/>ping diario, ventas, backup si toca"]
    end
    subgraph OC["orders.OrderCache._loop"]
        L["en reposo carga UNA arma por vuelta<br/>backoff exponencial ante errores"]
    end
    W["_wanted_weapons()<br/>armas de rivens visibles (más cerca del umbral de horas primero)<br/>+ armas de oportunidades"] --> L
    L --> CA[("caché de órdenes<br/>CACHE_MAX_AGE_S = 900")]
    CA --> D
    CA --> O
    CA --> S
    D --> Q["QUEUE"]
    C --> Q
    S --> Q
    L --> Q
```

`touch()` marca actividad de la UI: mientras el usuario opera, el cargador de fondo y los snapshots se frenan para no competir por la cola.

## 4. Ciclo de vida de un riven

```mermaid
stateDiagram-v2
    [*] --> Lote: add_lot (stock unveiled, solo local)
    Lote --> Borrador: Abrir (costo c/u precargado)
    [*] --> Borrador: Nuevo riven suelto
    Borrador --> Publicado: create() · create_direct_sale
    Lote --> Descartado: discard_from_lot (-1)
    Publicado --> Publicado: update() / republish() / repolarize()
    Publicado --> Oculto: visible = false
    Oculto --> Publicado: visible = true
    Publicado --> Publicado: autodrop baja el precio
    Publicado --> Vendido: close(sold_price)
    Publicado --> CerradoSinVenta: close(sin precio)
    Vendido --> [*]
    CerradoSinVenta --> [*]
```

Qué guarda cada paso (todo en `store.py`):
- `create`: evento `create`; si viene de un lote, `open_from_lot`; costo en `riven_costs`.
- `update` y `republish`: evento e historial de precio, y `_price_changed` propaga el precio nuevo a los cachés (órdenes en disco y mercado en memoria).
- `close`: evento `close` con copia del contrato (después desaparece de la API); si hubo venta, `log_sale_hours` (horas hasta vender, base para el umbral de baja y las ventas anónimas).

El borrador del modal Nuevo riven vive solo en memoria de la UI durante 10 s (`DRAFT_MS`).

## 5. Estimación de precio y alertas

```mermaid
flowchart LR
    A["riven del usuario"] --> P["pricing.estimate<br/>mediana ponderada por similitud<br/>(WEIGHTS por stat)"]
    CA[("caché de órdenes<br/>del arma")] --> P
    P --> E["precio estimado"]
    E --> SP["stockcheck.position<br/>barata / cara / estancada<br/>BAND 0,25 · MIN_DIFF 15"]
    E --> OP["opportunities.find<br/>% bajo el estimado, ganancia mínima<br/>máx. 3 por arma, CHEAP_FRACTION 0,3"]
    OP --> N["notificación kind=opp"]
    A --> R["reroll.py<br/>simulación de Kuva (KUVA_COSTS)"]
```

## 6. Baja automática de precio

Detalle de diseño en `DISENO_BAJA_AUTOMATICA.md`. Resumen del bucle:

```mermaid
flowchart TB
    T["cada 300 s"] --> E{"¿riven con autodrop<br/>y horas >= umbral?"}
    E -- no --> T
    E -- sí --> F{"¿órdenes en caché<br/>de menos de 900 s?"}
    F -- no --> T
    F -- sí --> G{"¿ya es el más barato?"}
    G -- sí --> H["reinicia sus horas"]
    G -- no --> I["nuevo = precio − amount<br/>nunca bajo el floor"]
    I --> J["_apply_drop: update_auction<br/>evento, historial, notificación<br/>reinicia horas, cache/autodrop.log"]
    J --> K["revert_drop disponible desde la notificación"]
```

Se baja un solo riven por pasada a propósito: son pedidos de escritura y no se quiere ráfaga.

## 7. Nube (cloud/)

```mermaid
flowchart LR
    APP["app"] -- "POST op: ping / sales / put / get / del / stats" --> B["backup.js"]
    APP -- "POST feedback / crash" --> F["feedback.js"]
    APP -- "GET /trend /top" --> API["api.js"]
    EB["EventBridge<br/>cron 0,6,12,18 h (+ :30)"] --> CO["collector.js<br/>foto de cada arma con rivens"]
    CO --> WM[("warframe.market")]
    CO --> H["history.js<br/>lo que desaparece = probable venta"]
    H --> M[("MongoDB")]
    B --> M
    F --> M
    F --> S3[("S3 privado")]
    API --> M
```

- El servidor de backup solo ve bytes cifrados; la clave sale del código de recuperación que tiene el usuario.
- Credenciales y cuenta AWS: ver notas locales (`.secrets/atlas.env`, perfil `cuenta_personal`). Recursos con tag `project=riven-stock`.

## 8. Actualización y recuperación ante fallas

```mermaid
sequenceDiagram
    participant A as App (Api)
    participant U as updater.py
    participant G as GitHub Releases
    participant X as proceso --aplicar
    A->>U: check_update
    U->>G: última versión
    A->>U: install_update
    U->>X: lanza aplicador y la app se cierra
    X->>X: backup de la versión actual, copia archivos
    X->>A: arranca la versión nueva
    A->>A: crashes: running.lock + health.json
    alt arranca bien
        A->>A: _mark_good (health.json)
    else falla al iniciar
        A->>X: rollback_target, vuelve a la versión anterior
    end
```

Publicar: `python tools/release.py X.Y.Z` (git limpio; toma "Sin publicar" del CHANGELOG, corre `tools/check_js.py`, arma zip e instalador, pushea, taggea y publica el release). Diseño en `DISENO_AUTOACTUALIZACION.md`.

## 9. Áreas de mejora detectadas

Ordenadas por lo que más conviene atacar. Son hallazgos de leer el código, no bugs confirmados.

1. **Sin tests automáticos.** Solo existe `tools/check_js.py` (sintaxis del JS). La lógica de dinero y decisión (`pricing`, `stockcheck`, `opportunities`, `autodrop_pass`, cálculo de Invertido/Balance en `store`) es pura o casi pura y sería barato de cubrir con unos pocos tests.
2. **`app.py` monolítico (unas 1400 líneas, clase `Api` con más de 100 métodos).** Mezcla API para la UI, los cinco bucles, nube, feedback y cierre. Separar los bucles y la nube en módulos propios bajaría el riesgo de tocar uno y romper otro.
3. **`ui/index.html` de unas 3900 líneas en un solo archivo.** HTML, CSS, JS, ayuda y recorridos juntos. Partir al menos el JS y el CSS en archivos facilita revisar cambios y que `check_js.py` señale mejor los errores.
4. **Archivos sobrantes en el repo:** `_backup/` (copias viejas de app, store, wfm_client, orders, updater) y `poc.py`. Git ya guarda el historial; son candidatos a borrar (hay que confirmarlo antes).
5. **`_wanted_weapons()` se recalcula varias veces** (snapshots, carga de caché, chequeo de caché completa) y cada vez consulta la base. Calcularlo una vez por pasada o cachearlo unos segundos.
6. **Los bucles no exponen su salud.** Si un hilo muere por una excepción no prevista, nada lo muestra (sin verificar si cada bucle captura todo). Un registro de "último ciclo OK" por bucle, visible en el diagnóstico, lo haría detectable.
7. **Autodrop de a uno por pasada (cada 5 min).** Con muchos rivens vencidos a la vez el ciclo completo se estira. Es una decisión consciente; revisar solo si el stock crece mucho.
8. **Contexto del proyecto desactualizado y sin copia.** `INDEX.md` y `CLAUDE.md` están gitignoreados (sin respaldo en GitHub) y partes de `INDEX.md` describen un estado viejo (por ejemplo "una sola pantalla, sin pestañas", estado del 2026-10-16). Este documento en `docs/` sí está versionado.
9. **Colector con Lambda de 10 s de timeout y reencadenado (`relaunch`).** Funciona, pero el costo y la cobertura por corrida conviene medirlos (ya hay una tarea de medir Mongo el 30/10).
10. **Tablas de errores y textos en tres lugares** (ERRS en index.html, lang_es.js, lang_en.js) sin chequeo automático de que cada clave exista en ambos idiomas. Un chequeo en `check_js.py` evitaría claves faltantes.

## 10. Cómo mantenerlo

- Al publicar una versión que cambie un flujo, un bucle, un módulo o la nube, actualizar la sección que corresponda y la fecha/versión de la cabecera.
- Si cambia una constante citada acá (periodos, umbrales, tamaños), actualizar el número.
- Al resolver un punto de la sección 9, borrarlo; al encontrar uno nuevo, sumarlo.
