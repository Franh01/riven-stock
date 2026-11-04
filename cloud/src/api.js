// API de lectura (Function URL pública). GET /trend?weapon=<slug>&days=<n>, GET /sales?weapon=<slug>&days=<n>
// (ventas recientes, para los comparables del estimado) y GET /top (lo más movido en 24 h).
const { snapshots, collection } = require("./db");
const history = require("./history");
const { salesSeries, DAY } = require("./series");

// Ventas que cuentan: sin las falsas del corte en 100 y con confianza alta o media (igual que el modelo de precio).
const REAL = { suspect: { $exists: false }, price: { $gt: 0 }, confidence: { $in: ["alta", "media"] } };
const SALES_WINDOW = 7;

const json = (status, body, cache = "public, max-age=300") => ({
  statusCode: status,
  headers: { "Content-Type": "application/json", "Cache-Control": cache, "Access-Control-Allow-Origin": "*" },
  body: JSON.stringify(body),
});

// Armas con más ventas inferidas en las últimas 24 h y con más publicaciones nuevas (la búsqueda de la API corta en 100, así que el total de órdenes no sirve).
async function top(limit) {
  const { sales } = await history.ensure();
  const since = new Date(Date.now() - 86400000);
  const sold = await sales.aggregate([
    { $match: { detected_at: { $gte: since }, suspect: { $exists: false } } },   // suspect: ventas falsas del corte en 100 (marcadas a mano)
    { $group: { _id: "$weapon", sold: { $sum: 1 }, prices: { $push: "$price" } } },
    { $sort: { sold: -1 } },
    { $limit: limit },
  ]).toArray();
  const { listings } = await history.ensure();
  const orders = await listings.aggregate([
    { $match: { created: { $gte: since.toISOString() } } },
    { $group: { _id: "$weapon", n: { $sum: 1 } } },
    { $sort: { n: -1 } },
    { $limit: limit },
  ]).toArray();
  const median = (a) => { const b = [...a].sort((x, y) => x - y); return b[Math.floor(b.length / 2)]; };
  const st = await (await collection("collector_state")).find({ n: { $exists: true } }, { projection: { n: 1, truncated: 1 } }).toArray();
  const stats = { weapons: st.length, truncated: st.filter((x) => x.truncated).length, capped: st.filter((x) => x.n >= 100).length };
  return {
    stats,
    sold: sold.map((d) => ({ weapon: d._id, sold: d.sold, median: median(d.prices) })),
    orders: orders.map((d) => ({ weapon: d._id, orders: d.n })),
    since: since.toISOString(),
  };
}

exports.handler = async (event) => {
  const q = event.queryStringParameters || {};
  if ((event.rawPath || "").replace(/\/+$/, "") === "/top") {
    const limit = Math.min(Math.max(parseInt(q.limit, 10) || 10, 1), 30);
    return json(200, await top(limit));
  }
  const weapon = String(q.weapon || "");
  if (!/^[a-z0-9_]{2,60}$/.test(weapon)) return json(400, { error: "weapon inválida" }, "no-store");
  const days = Math.min(Math.max(parseInt(q.days, 10) || 90, 1), 730);
  const now = Date.now();
  const from = new Date(now - days * DAY).toISOString().slice(0, 10);
  const { sales } = await history.ensure();
  if ((event.rawPath || "").replace(/\/+$/, "") === "/sales") {
    const rows = await sales
      .find({ weapon, detected_at: { $gte: new Date(now - days * DAY) }, ...REAL },
        { projection: { price: 1, attrs: 1, rolls: 1, mr: 1, rank: 1, seller: 1, detected_at: 1 } })
      .sort({ detected_at: -1 })
      .limit(400)
      .toArray();
    return json(200, { sales: rows.map((d) => ({ id: d._id, price: d.price, attrs: d.attrs || [], rolls: d.rolls, mr: d.mr, rank: d.rank, seller: d.seller, at: d.detected_at })) });
  }
  const col = await snapshots();
  const points = await col
    .find({ weapon, day: { $gte: from } }, { projection: { _id: 0, day: 1, n_orders: 1, n_online: 1, min_price: 1, median: 1 } })
    .sort({ day: 1 })
    .toArray();
  const sold = await sales
    .find({ weapon, detected_at: { $gte: new Date(Date.parse(from + "T00:00:00Z") - (SALES_WINDOW - 1) * DAY) }, ...REAL },
      { projection: { _id: 0, price: 1, seller: 1, detected_at: 1 } })
    .toArray();
  const series = salesSeries(sold.map((d) => ({ price: d.price, seller: d.seller, at: d.detected_at })), from, new Date(now).toISOString().slice(0, 10), SALES_WINDOW);
  return json(200, { points, sales: series, sales_window: SALES_WINDOW });
};
