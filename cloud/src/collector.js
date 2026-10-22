// Corre 4 veces por día (EventBridge): una foto de cada arma con rivens en warframe.market.
const { snapshots } = require("./db");
const history = require("./history");

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

const CUT = 480;           // la búsqueda de warframe.market devuelve como máximo ~500
const MARGIN_MS = 60000;   // tiempo que se deja para cerrar y relanzarse
const MAX_CHAIN = 30;      // tope de relevos encadenados en un mismo día (evita bucles infinitos)

async function relaunch(chain) {
  const { LambdaClient, InvokeCommand } = require("@aws-sdk/client-lambda");
  await new LambdaClient({}).send(new InvokeCommand({
    FunctionName: process.env.AWS_LAMBDA_FUNCTION_NAME,
    InvocationType: "Event",
    Payload: JSON.stringify({ chain: chain + 1 }),
  }));
}

exports.handler = async (event, context) => {
  const chain = event?.chain || 0;
  const day = new Date().toISOString().slice(0, 10);
  const slot = `${day}T${String(Math.floor(new Date().getUTCHours() / 6) * 6).padStart(2, "0")}`;   // pasada de 6 horas
  const weapons = (await get("/v2/riven/weapons")).data.map((w) => w.slug);
  const col = await snapshots();
  // Cola de pendientes: lo que ya está guardado hoy no se repite, así cada corrida retoma donde quedó la anterior.
  const { state } = await history.ensure();
  const done = new Set((await state.find({ slot }, { projection: { _id: 1 } }).toArray()).map((d) => d._id));
  let pending = weapons.filter((w) => !done.has(w));
  const start = pending.length;
  const deadline = () => context.getRemainingTimeInMillis() - MARGIN_MS;
  let lastStart = 0;
  let lastError = "";
  let round = 0;

  while (pending.length && deadline() > 0) {
    const queue = pending;
    pending = [];
    let next = 0;
    // Tres pedidos en vuelo a la vez; las salidas se espacian para no pasar de ~3 por segundo.
    const worker = async () => {
      while (next < queue.length) {
        const weapon = queue[next++];
        if (deadline() <= 0) { pending.push(weapon); continue; }
        const wait = lastStart + PAUSE_MS - Date.now();
        lastStart = Math.max(Date.now(), lastStart + PAUSE_MS);
        if (wait > 0) await sleep(wait);
        try {
          const qs = new URLSearchParams({ type: "riven", weapon_url_name: weapon, buyout_policy: "direct", sort_by: "price_asc" });
          let auctions = (await get(`/v1/auctions/search?${qs}`)).payload.auctions;
          let gap = null;
          if (auctions.length >= CUT) {   // la búsqueda corta en ~500: se pide también desde las más caras y se une
            qs.set("sort_by", "price_desc");
            const caras = (await get(`/v1/auctions/search?${qs}`)).payload.auctions;
            const ids = new Set(auctions.map((a) => a.id));
            const lo = Math.max(...auctions.map((a) => a.buyout_price ?? 0));
            const hi = Math.min(...caras.map((a) => a.buyout_price ?? Infinity));
            auctions = auctions.concat(caras.filter((a) => !ids.has(a.id)));
            gap = lo < hi ? { lo, hi } : { lo: 1, hi: 0 };   // sin franja vista -> {1,0} (vacía): se vio todo el mercado
          }
          await col.updateOne({ weapon, day }, { $set: { weapon, day, ...summarize(auctions) } }, { upsert: true });
          await history.record(weapon, auctions, new Date(), gap);
          await state.updateOne({ _id: weapon }, { $set: { slot } });
        } catch (e) {
          lastError = `${weapon}: ${e.message}`;
          pending.push(weapon);   // vuelve a la cola para la próxima ronda
        }
      }
    };
    await Promise.all([worker(), worker(), worker()]);
    console.log(JSON.stringify({ round: ++round, saved: queue.length - pending.length, pending: pending.length }));
    // Si falló algo, se espera antes de reintentar (más cada ronda) para no seguir golpeando el límite.
    if (pending.length && deadline() > 0) await sleep(Math.min(5000 * round, 30000, Math.max(0, deadline())));
  }

  const result = { slot, total: weapons.length, skipped: done.size, saved: start - pending.length, pending: pending.length, chain, lastError };
  if (pending.length) {
    if (chain < MAX_CHAIN) { await relaunch(chain); result.relaunched = true; }
    else console.error("Se agotaron los relevos con armas pendientes", pending.length);
  }
  console.log(JSON.stringify(result));
  return result;
};
