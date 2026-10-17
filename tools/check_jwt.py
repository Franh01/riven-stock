"""Verifica el JWT de warframe.market que está en la variable de entorno WFM_JWT.

Lo usa el instalador. Imprime el nombre en el juego de la cuenta y sale con 0 si el token
sirve; si no, imprime el motivo y sale con 1. El token nunca se imprime.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wfm_client import AuthError, WFMClient, WFMError  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

token = os.environ.get("WFM_JWT", "").strip()
if not token:
    print("No llegó ningún token.")
    sys.exit(1)
try:
    me = WFMClient(jwt=token).me()
except AuthError:
    print("warframe.market rechazó el token (401/403): copiá uno nuevo.")
    sys.exit(1)
except WFMError as e:
    print(f"No se pudo verificar: {e}")
    sys.exit(1)
except Exception as e:  # sin conexión, DNS, etc.
    print(f"No se pudo conectar con warframe.market: {e}")
    sys.exit(1)
print(me.get("ingameName") or me.get("slug") or "?")
