// API de lectura (Function URL pública). GET /trend?weapon=<slug>&days=<n> y GET /top (lo más movido en 24 h).
const { snapshots, collection } = require("./db");
const history = require("./history");

const json = (status, body, cache = "public, max-age=300") => ({
  statusCode: status,
  headers: { "Content-Type": "application/json", "Cache-Control": cache, "Access-Control-Allow-Origin": "*" },
  body: JSON.stringify(body),
});

// Armas con más ventas inferidas en las últimas 24 h y con más publicaciones nuevas (la búsqueda de la API corta en 500, así que el total de órdenes no sirve).
async function top(limit) {
  const { sales } = await history.ensure();
  const since = new Date(Date.now() - 86400000);
  const sold = await sales.aggregate([
    { $match: { detected_at: { $gte: since } } },
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
  const stats = { weapons: st.length, truncated: st.filter((x) => x.truncated).length, ge480: st.filter((x) => x.n >= 480).length };
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
  const from = new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);
  const col = await snapshots();
  const points = await col
    .find({ weapon, day: { $gte: from } }, { projection: { _id: 0, day: 1, n_orders: 1, n_online: 1, min_price: 1, median: 1 } })
    .sort({ day: 1 })
    .toArray();
  return json(200, { points });
};
