"""Prueba de concepto (Fase 1), solo lectura.

  python poc.py search rubico critical_chance,critical_damage [negativos]
  python poc.py me
"""

import sys

import requests

from wfm_client import BASE_URL, HEADERS, AuthError, WFMClient, summarize

sys.stdout.reconfigure(encoding="utf-8")


def cmd_search(weapon, positives, negatives=None):
    c = WFMClient()
    pos = positives.split(",")
    neg = negatives.split(",") if negatives else None
    top = c.top_direct_ingame(weapon, pos, neg)
    print(f"{len(top)} ventas directas ingame más baratas para {weapon} [{positives}]"
          + (f" neg [{negatives}]" if negatives else ""))
    for a in top:
        print(summarize(a))
    if top:
        prices = [a["buyout_price"] for a in top]
        print(f"min {min(prices)}p  mediana {sorted(prices)[len(prices) // 2]}p")


def probe_auth(jwt):
    """Prueba formatos de auth contra /v2/me. Imprime solo códigos de estado."""
    variants = {
        "Authorization: Bearer <jwt>": {"headers": {"Authorization": f"Bearer {jwt}"}},
        "Authorization: JWT <jwt>": {"headers": {"Authorization": f"JWT {jwt}"}},
        "Authorization: <jwt>": {"headers": {"Authorization": jwt}},
        "Cookie JWT=<jwt>": {"cookies": {"JWT": jwt}},
    }
    for name, extra in variants.items():
        res = requests.get(f"{BASE_URL}/v2/me", headers={**HEADERS, **extra.get("headers", {})},
                           cookies=extra.get("cookies"), timeout=20)
        print(f"  {name:32} -> {res.status_code}")


def cmd_me():
    c = WFMClient()
    if not c.jwt:
        sys.exit("Falta WFM_JWT en .env")
    try:
        me = c.me()
    except AuthError as e:
        print(f"Bearer falló ({e}). Probando otros formatos:")
        probe_auth(c.jwt)
        return
    slug = me.get("slug")
    print(f"Logueado como {me.get('ingameName')} (slug {slug}, status {me.get('status')})")
    auctions = c.profile_auctions(slug)
    direct = [a for a in auctions if a["is_direct_sell"]]
    print(f"{len(auctions)} contratos, {len(direct)} ventas directas:")
    for a in direct:
        print(f"  {a['id']}  {summarize(a)}  visible={a['visible']} closed={a['closed']}")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "search":
        cmd_search(*sys.argv[2:5])
    elif sys.argv[1:] == ["me"]:
        cmd_me()
    else:
        sys.exit(__doc__)
