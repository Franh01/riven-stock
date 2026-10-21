// Copias de seguridad cifradas y conteo de instalaciones activas (Function URL pública, POST JSON).
// El servidor nunca ve los datos en claro: el cliente cifra con una clave que sale de un código que solo tiene el usuario.
//   {op:"put", id, blob, v}   guarda/reemplaza la copia (blob en base64; id = hex de 64 derivado del código)
//   {op:"get", id}            devuelve la copia
//   {op:"del", id}            borra la copia
//   {op:"ping", iid, v}       registra una instalación activa (iid = UUID anónimo)
//   {op:"stats"}              cuántas instalaciones hubo activas en los últimos 30 días
const { collection } = require("./db");

const MAX_BLOB = 4 * 1024 * 1024;   // bytes ya cifrados
const reply = (status, body) => ({
  statusCode: status,
  headers: { "Content-Type": "application/json", "Cache-Control": "no-store", "Access-Control-Allow-Origin": "*" },
  body: JSON.stringify(body),
});
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

  if (req.op === "put") {
    if (!ID.test(req.id || "") || typeof req.blob !== "string") return reply(400, { error: "pedido inválido" });
    const buf = Buffer.from(req.blob, "base64");
    if (!buf.length || buf.length > MAX_BLOB) return reply(413, { error: "tamaño inválido" });
    const col = await collection("backups");
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
    await (await collection("installs")).updateOne({ _id: req.iid },
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
