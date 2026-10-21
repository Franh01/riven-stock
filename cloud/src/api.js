// API de lectura (Function URL pública). Solo GET /trend?weapon=<slug>&days=<n>.
const { snapshots } = require("./db");

const json = (status, body, cache = "public, max-age=300") => ({
  statusCode: status,
  headers: { "Content-Type": "application/json", "Cache-Control": cache, "Access-Control-Allow-Origin": "*" },
  body: JSON.stringify(body),
});

exports.handler = async (event) => {
  const q = event.queryStringParameters || {};
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
