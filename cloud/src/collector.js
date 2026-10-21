// Corre una vez por día (EventBridge): una foto de cada arma con rivens en warframe.market.
const { snapshots } = require("./db");

const BASE = "https://api.warframe.market";
const HEADERS = { Platform: "pc", Language: "en", Accept: "application/json", "User-Agent": "riven-stock-collector/1.0" };
const PAUSE_MS = 400;   // ~2.5 pedidos por segundo, por debajo del límite de 3

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function get(path, retries = 3) {
  for (let i = 0; ; i++) {
    const res = await fetch(BASE + path, { headers: HEADERS });
    if (res.status === 429 && i < retries) { await sleep(5000 * (i + 1)); continue; }
    if (!res.ok) throw new Error(`${res.status} en ${path}`);
    return res.json();
  }
}

// Misma cuenta que el snapshot local: mínimo y mediana de las ventas directas visibles.
function summarize(auctions) {
  const live = auctions.filter((a) => a.is_direct_sell && a.visible !== false && !a.closed && !a.private);
  const prices = live.map((a) => a.buyout_price).sort((a, b) => a - b);
  const online = live.filter((a) => ["ingame", "online"].includes(a.owner?.status)).length;
  return {
    n_orders: prices.length,
    n_online: online,
    min_price: prices.length ? prices[0] : null,
    median: prices.length ? prices[Math.floor(prices.length / 2)] : null,
  };
}

exports.handler = async () => {
  const day = new Date().toISOString().slice(0, 10);
  const weapons = (await get("/v2/riven/weapons")).data.map((w) => w.slug);
  const col = await snapshots();
  let ok = 0;
  const failed = [];
  for (const weapon of weapons) {
    try {
      const qs = new URLSearchParams({ type: "riven", weapon_url_name: weapon, buyout_policy: "direct", sort_by: "price_asc" });
      const auctions = (await get(`/v1/auctions/search?${qs}`)).payload.auctions;
      await col.updateOne({ weapon, day }, { $set: { weapon, day, ...summarize(auctions) } }, { upsert: true });
      ok++;
    } catch (e) {
      failed.push(`${weapon}: ${e.message}`);
    }
    await sleep(PAUSE_MS);
  }
  console.log(JSON.stringify({ day, total: weapons.length, ok, failed: failed.length, sample: failed.slice(0, 5) }));
  if (ok === 0) throw new Error("No se pudo guardar ninguna arma: " + failed[0]);
  return { day, ok, failed: failed.length };
};
