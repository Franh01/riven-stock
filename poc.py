"""Prueba de concepto (Fase 1), solo lectura.

  python poc.py search rubico critical_chance,critical_damage [negativos]
  python poc.py me
"""

import sys

from wfm_client import AuthError, WFMClient, summarize

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


def cmd_me():
    c = WFMClient()
    try:
        me = c.me()
        auctions = c.my_auctions()
    except AuthError as e:
        sys.exit(f"{e}. Copiá un JWT nuevo desde el navegador a .env.")
    print(f"Logueado como {me['ingameName']} (slug {me['slug']}, MR {me.get('masteryRank')})")
    direct = [a for a in auctions if a["is_direct_sell"]]
    print(f"{len(auctions)} contratos, {len(direct)} ventas directas "
          f"({sum(a['visible'] for a in direct)} visibles):")
    for a in sorted(direct, key=lambda a: not a["visible"]):
        print(f"  {a['id']}  {'   ' if a['visible'] else 'OCU'}  {summarize(a)}")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "search":
        cmd_search(*sys.argv[2:5])
    elif sys.argv[1:] == ["me"]:
        cmd_me()
    else:
        sys.exit(__doc__)
