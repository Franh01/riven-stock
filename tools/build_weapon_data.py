"""Genera data/weapon_stats.json (datos por arma para el estimador) desde WFCD/warframe-items.

Uso: python tools/build_weapon_data.py   (necesita internet; el resultado se commitea)
Clave = slug de warframe.market (nombre en minúsculas con _). Solo se guardan los campos que usa pricing.py.
"""
import json
import re
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json/"
FILES = ["Primary", "Secondary", "Melee", "Arch-Gun", "Arch-Melee"]
OUT = Path(__file__).resolve().parent.parent / "data" / "weapon_stats.json"
PHYS = ("impact", "puncture", "slash")


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def main():
    out = {}
    for f in FILES:
        with urllib.request.urlopen(BASE + f + ".json", timeout=60) as r:
            items = json.load(r)
        for it in items:
            atks = [a for a in (it.get("attacks") or []) if a.get("damage")]
            if not atks or it.get("category") == "Mods":
                continue
            a = next((x for x in atks if "normal" in x["name"].lower()), atks[0])
            dmg = {k.lower(): v for k, v in a["damage"].items() if v}
            tot = sum(dmg.values())
            if not tot:
                continue
            out[slug(it["name"])] = {
                "type": it.get("type"), "total": round(tot, 1),
                "share": {k: round(v / tot, 3) for k, v in sorted(dmg.items(), key=lambda t: -t[1])},
                "crit": a.get("crit_chance"), "critx": a.get("crit_mult"), "status": a.get("status_chance"),
                "rate": a.get("speed"), "shot": a.get("shot_type"),
                "multishot": it.get("multishot"),
            }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    print(len(out), "armas ->", OUT)


if __name__ == "__main__":
    main()
