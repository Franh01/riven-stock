// Copias de seguridad cifradas y conteo de instalaciones activas (Function URL pública, POST JSON).
// El servidor nunca ve los datos en claro: el cliente cifra con una clave que sale de un código que solo tiene el usuario.
//   {op:"put", id, blob, v}   guarda/reemplaza la copia (blob en base64; id = hex de 64 derivado del código)
//   {op:"get", id}            devuelve la copia
//   {op:"del", id}            borra la copia
//   {op:"ping", iid, v}       registra una instalación activa (iid = UUID anónimo)
//   {op:"stats"}              cuántas instalaciones hubo activas en los últimos 30 días
const { createHash } = require("crypto");
const { collection } = require("./db");

const MAX_BLOB = 4 * 1024 * 1024;   // bytes ya cifrados
const reply = (status, body) => ({
  statusCode: status,
  headers: { "Content-Type": "application/json", "Cache-Control": "no-store", "Access-Control-Allow-Origin": "*" },
  body: JSON.stringify(body),
});
// Límites anti-abuso (la Function URL es pública): por IP y por hora, y topes globales para no llenar el cluster gratuito.
const HOURLY = { put: 20, get: 30, del: 20, ping: 30, stats: 120 };
const MAX_BACKUPS = 3000;
const MAX_NEW_INSTALLS_PER_IP_DAY = 20;
let indexed;
async function hit(op, ip) {
  const lim = await collection("limits");
  indexed = indexed || lim.createIndex({ exp: 1 }, { expireAfterSeconds: 0 }).catch(() => {});
  await indexed;
  const hourKey = new Date().toISOString().slice(0, 13);
  const id = `bk:${hourKey}:${op}:${createHash("sha256").update(ip).digest("hex").slice(0, 24)}`;
  const r = await lim.findOneAndUpdate({ _id: id }, { $inc: { n: 1 }, $setOnInsert: { exp: new Date(Date.now() + 2 * 3600000) } }, { upsert: true, returnDocument: "after" });
  return r.n <= (HOURLY[op] || 30);
}
const ID = /^[0-9a-f]{64}$/;
const IID = /^[0-9a-f-]{32,40}$/;
const VER = /^[0-9A-Za-z.\-]{1,20}$/;

exports.handler = async (event) => {
  let req;
  try {
    const raw = event.isBase64Encoded ? Buffer.from(event.body || "", "base64").toString() : event.body || "";
    req = JSON.parse(raw);
  } catch { return reply(400, { error: "json inválido" }); }
  const now = new Date();
  const ip = event.requestContext?.http?.sourceIp || "unknown";
  if (!(await hit(String(req.op).slice(0, 8), ip))) return reply(429, { error: "rate_limited" });

  if (req.op === "put") {
    if (!ID.test(req.id || "") || typeof req.blob !== "string") return reply(400, { error: "pedido inválido" });
    const buf = Buffer.from(req.blob, "base64");
    if (!buf.length || buf.length > MAX_BLOB) return reply(413, { error: "tamaño inválido" });
    const col = await collection("backups");
    if (!(await col.countDocuments({ _id: req.id, }, { limit: 1 })) && (await col.estimatedDocumentCount()) >= MAX_BACKUPS) return reply(503, { error: "full" });
    await col.updateOne({ _id: req.id },
      { $set: { blob: buf, size: buf.length, v: VER.test(req.v || "") ? req.v : null, updated: now }, $setOnInsert: { created: now } },
      { upsert: true });
    return reply(200, { ok: true, at: now.toISOString(), size: buf.length });
  }
  if (req.op === "get") {
    if (!ID.test(req.id || "")) return reply(400, { error: "pedido inválido" });
    const doc = await (await collection("backups")).findOne({ _id: req.id });
    if (!doc) return reply(404, { error: "no_backup" });
    return reply(200, { blob: doc.blob.buffer ? Buffer.from(doc.blob.buffer).toString("base64") : "", at: doc.updated.toISOString() });
  }
  if (req.op === "del") {
    if (!ID.test(req.id || "")) return reply(400, { error: "pedido inválido" });
    await (await collection("backups")).deleteOne({ _id: req.id });
    return reply(200, { ok: true });
  }
  if (req.op === "ping") {
    if (!IID.test(req.iid || "")) return reply(400, { error: "pedido inválido" });
    const inst = await collection("installs");
    if (!(await inst.countDocuments({ _id: req.iid }, { limit: 1 }))) {
      const lim = await collection("limits");
      const k = `newinst:${now.toISOString().slice(0, 10)}:${createHash("sha256").update(ip).digest("hex").slice(0, 24)}`;
      const r = await lim.findOneAndUpdate({ _id: k }, { $inc: { n: 1 }, $setOnInsert: { exp: new Date(Date.now() + 2 * 86400000) } }, { upsert: true, returnDocument: "after" });
      if (r.n > MAX_NEW_INSTALLS_PER_IP_DAY) return reply(429, { error: "rate_limited" });
    }
    await inst.updateOne({ _id: req.iid },
      { $set: { last_seen: now, v: VER.test(req.v || "") ? req.v : null }, $setOnInsert: { first_seen: now } },
      { upsert: true });
    return reply(200, { ok: true });
  }
  if (req.op === "stats") {
    const col = await collection("installs");
    const since = new Date(Date.now() - 30 * 86400000);
    const [active, total] = await Promise.all([col.countDocuments({ last_seen: { $gte: since } }), col.estimatedDocumentCount()]);
    return reply(200, { active, total });
  }
  return reply(400, { error: "op desconocida" });
};
