// Corre una vez por día (EventBridge): una foto de cada arma con rivens en warframe.market.
const { snapshots } = require("./db");

const BASE = "https://api.warframe.market";
const HEADERS = { Platform: "pc", Language: "en", Accept: "application/json", "User-Agent": "riven-stock-collector/1.0" };
const PAUSE_MS = 350;   // separación entre inicios de pedido (~2.9 por segundo, tope de la API: 3)

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function get(path, retries = 3) {
  for (let i = 0; ; i++) {
    const res = await fetch(BASE + path, { headers: HEADERS, signal: AbortSignal.timeout(20000) });
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
  // Si una corrida anterior del día quedó a medias, retoma solo lo que falta.
  const done = new Set((await col.find({ day }, { projection: { weapon: 1 } }).toArray()).map((d) => d.weapon));
  const queue = weapons.filter((w) => !done.has(w));
  let ok = 0;
  const failed = [];
  let next = 0;
  let lastStart = 0;

  // Tres pedidos en vuelo a la vez; las salidas se espacian para no pasar de ~3 por segundo.
  async function worker() {
    while (next < queue.length) {
      const weapon = queue[next++];
      const wait = lastStart + PAUSE_MS - Date.now();
      lastStart = Math.max(Date.now(), lastStart + PAUSE_MS);
      if (wait > 0) await sleep(wait);
      try {
        const qs = new URLSearchParams({ type: "riven", weapon_url_name: weapon, buyout_policy: "direct", sort_by: "price_asc" });
        const auctions = (await get(`/v1/auctions/search?${qs}`)).payload.auctions;
        await col.updateOne({ weapon, day }, { $set: { weapon, day, ...summarize(auctions) } }, { upsert: true });
        ok++;
      } catch (e) {
        failed.push(`${weapon}: ${e.message}`);
      }
      if ((ok + failed.length) % 50 === 0) console.log(JSON.stringify({ progress: ok + failed.length, of: queue.length }));
    }
  }
  await Promise.all([worker(), worker(), worker()]);

  console.log(JSON.stringify({ day, total: weapons.length, skipped: done.size, ok, failed: failed.length, sample: failed.slice(0, 5) }));
  if (queue.length && ok === 0) throw new Error("No se pudo guardar ninguna arma: " + failed[0]);
  return { day, ok, failed: failed.length };
};
