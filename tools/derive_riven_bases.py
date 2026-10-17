"""Genera data/riven_bases.json: valor base de cada stat de riven por tipo de arma.

Fuente: el export público oficial de DE (ExportUpgrades, entradas "Randomized"). Los tags de
DE (ej. "WeaponCritChanceMod") coinciden con el `gameRef` de /v2/riven/attributes de
warframe.market, así que se cruzan por ahí.

Se usa para sugerir el nombre del riven: el orden de los stats en el nombre lo da su
"modificador aleatorio" = valor / valor base (de mayor a menor). Solo importa la proporción
entre stats del mismo tipo, así que las unidades del export alcanzan.

    python tools/derive_riven_bases.py
"""

import json
import lzma
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wfm_client import WFMClient  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "riven_bases.json"
INDEX_URL = "https://origin.warframe.com/PublicExport/index_en.txt.lzma"
MANIFEST_URL = "https://content.warframe.com/PublicExport/Manifest/{}"

# uniqueName del riven en el export -> rivenType de warframe.market
TYPES = {
    "/Lotus/Upgrades/Mods/Randomized/LotusRifleRandomModRare": "rifle",
    "/Lotus/Upgrades/Mods/Randomized/LotusShotgunRandomModRare": "shotgun",
    "/Lotus/Upgrades/Mods/Randomized/LotusPistolRandomModRare": "pistol",
    "/Lotus/Upgrades/Mods/Randomized/PlayerMeleeWeaponRandomModRare": "melee",
    "/Lotus/Upgrades/Mods/Randomized/LotusModularMeleeRandomModRare": "zaw",
    "/Lotus/Upgrades/Mods/Randomized/LotusModularPistolRandomModRare": "kitgun",
    "/Lotus/Upgrades/Mods/Randomized/LotusArchgunRandomModRare": "archgun",
}


# Tags de melee que en warframe.market comparten slug con los de armas a distancia.
TAG_ALIASES = {
    "WeaponMeleeDamageMod": "base_damage_/_melee_damage",
    "WeaponMeleeFactionDamageCorpus": "damage_vs_corpus",
    "WeaponMeleeFactionDamageGrineer": "damage_vs_grineer",
    "WeaponMeleeFactionDamageInfested": "damage_vs_infested",
}


def decode_lzma(raw):
    """El índice de DE trae un header LZMA con tamaño inválido: se decodifica en modo raw."""
    p = raw[0]
    filters = [{"id": lzma.FILTER_LZMA1, "dict_size": int.from_bytes(raw[1:5], "little"),
                "lc": p % 9, "lp": (p // 9) % 5, "pb": p // 45}]
    return lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters).decompress(raw[13:])


def main():
    index = decode_lzma(requests.get(INDEX_URL, timeout=30).content).decode()
    name = next(line for line in index.splitlines() if line.startswith("ExportUpgrades_en.json"))
    text = requests.get(MANIFEST_URL.format(name.strip()), timeout=60).text
    upgrades = json.loads(text.replace("\r", "").replace("\n", " "), strict=False)["ExportUpgrades"]

    by_ref = {a["gameRef"]: a["slug"] for a in WFMClient().riven_attributes() if a.get("gameRef")}
    bases, unknown = {}, set()
    for mod in upgrades:
        rtype = TYPES.get(mod.get("uniqueName"))
        if not rtype:
            continue
        for entry in mod.get("upgradeEntries", []):
            slug = by_ref.get(entry["tag"]) or TAG_ALIASES.get(entry["tag"])
            if not slug:
                unknown.add(entry["tag"])
                continue
            bases.setdefault(rtype, {})[slug] = abs(entry["upgradeValues"][0]["value"])

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(bases, indent=1, sort_keys=True), encoding="utf-8")
    print(f"ok: {OUT} | tipos: {sorted(bases)} | stats por tipo: { {t: len(s) for t, s in bases.items()} }")
    if unknown:
        print("tags de DE sin equivalente en warframe.market:", sorted(unknown))


if __name__ == "__main__":
    main()
