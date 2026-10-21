# Revisión de ciberseguridad (2026-10-21)

## Resuelto
- **Abuso de la Function URL de copias (backup.js)**: era pública y sin límites; alguien podía llenar el cluster gratuito con copias de 4 MB o inflar el contador de usuarios activos. Ahora hay tope por IP y por hora para cada operación, tope global de 3000 copias y máximo de 20 instalaciones nuevas por IP por día. Desplegado y probado (429 al pasarse).
- **Dependencias**: pip-audit marcó certifi 2026.7.22; actualizado a 2026.10.19 en el entorno de compilación. npm audit de la nube: 0 vulnerabilidades. (pip 26.1.2 también marcado, pero no se incluye en la app.)

## Verificado, sin cambios
- **Copia en la nube**: código de recuperación de 130 bits, AES-GCM en el cliente; el servidor solo guarda bytes opacos y el id es un HMAC del código (no se puede adivinar ni deducir la clave).
- **Bucket S3 de feedback**: bloqueo de acceso público total, cifrado AES256, borrado a los 180 días, solo `s3:PutObject` para la Lambda.
- **Feedback**: valida firma real de PNG/JPG, tamaños, límite por instalación e IP, tope diario global; logs sanitizados en el cliente (token, usuario de Windows, código de recuperación).
- **IAM**: un solo rol de Lambda con permisos mínimos (PutObject al bucket e invocar al colector).
- **Usuario de Mongo**: `riven_app` solo con readWrite sobre la base `riven_stock`.
- **Secretos**: `.env`, `.secrets` y los datos no están en el repo.
- **Actualizador**: verifica sha256 antes de instalar.

## Riesgos aceptados / pendientes
- **Atlas con 0.0.0.0/0**: necesario porque las Lambdas no tienen IP fija; mitigado con contraseña larga y usuario de mínimo alcance. Alternativa futura: VPC con NAT e IP fija (costo mensual) o Atlas Data API.
- **Private key de Atlas**: Fran decidió no rotarla (aceptado).
- **sha256 del instalador**: está en el mismo release de GitHub que el archivo, así que no protege si se compromete la cuenta de GitHub. Mitigación: 2FA en la cuenta. Mejora real: firma Authenticode (certificado de pago; también quita el aviso de SmartScreen).
- **Token de warframe.market**: se guarda en texto plano en `%APPDATA%\RivenStock\.env` (solo accesible por el usuario de Windows). Mejora posible: cifrarlo con DPAPI.
- **CORS `*`**: sin consecuencia, las URL no usan cookies ni credenciales.
