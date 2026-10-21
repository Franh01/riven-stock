// Sugerencias y reportes de bugs (Function URL pública, POST JSON).
//   {iid, v, kind:"suggestion"|"bug"|"crash", text, contact?, logs?, shots?:[{name, data}]}
// Capturas: base64 de PNG/JPG (se valida la firma real del archivo). Logs: texto en base64 (gzip opcional).
// Los adjuntos van a S3 (bucket privado); el reporte, a Mongo. Límites por instalación y por IP, y topes globales.
const { createHash } = require("crypto");
const { gunzipSync } = require("zlib");
const { S3Client, PutObjectCommand } = require("@aws-sdk/client-s3");
const { collection } = require("./db");

const s3 = new S3Client({});
const BUCKET = process.env.FEEDBACK_BUCKET;

const COOLDOWN_MS = 10 * 60 * 1000;   // 1 envío cada 10 min por instalación y por IP
const DAILY_PER_IP = 10;
const DAILY_GLOBAL = 300;             // tope duro: acota el costo si alguien insiste desde muchas IP
const MAX_TEXT = 4000;
const MAX_CONTACT = 120;
const MAX_SHOTS = 3;
const MAX_SHOT = 1.5 * 1024 * 1024;   // bytes por captura
const MAX_LOGS = 400 * 1024;          // bytes de log ya descomprimido

const reply = (status, body) => ({
  statusCode: status,
  headers: { "Content-Type": "application/json", "Cache-Control": "no-store", "Access-Control-Allow-Origin": "*" },
  body: JSON.stringify(body),
});
const IID = /^[0-9a-f-]{32,40}$/;
const VER = /^[0-9A-Za-z.\-]{1,20}$/;

function imageKind(buf) {
  if (buf.length > 8 && buf.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) return "png";
  if (buf.length > 3 && buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) return "jpg";
  return null;
}
let indexed;   // el índice TTL borra solo los contadores vencidos (idempotente: se crea una vez por arranque)
const ensureIndex = async (col) => { indexed = indexed || col.createIndex({ exp: 1 }, { expireAfterSeconds: 0 }).catch(() => {}); return indexed; };
const hash = (s) => createHash("sha256").update(String(s)).digest("hex").slice(0, 32);

exports.handler = async (event) => {
  let req;
  try {
    const raw = event.isBase64Encoded ? Buffer.from(event.body || "", "base64").toString() : event.body || "";
    req = JSON.parse(raw);
  } catch { return reply(400, { error: "bad_request" }); }

  const kind = req.kind;
  const text = typeof req.text === "string" ? req.text.trim() : "";
  if (!IID.test(req.iid || "") || (kind !== "suggestion" && kind !== "bug" && kind !== "crash") || text.length < (kind === "crash" ? 1 : 5) || text.length > MAX_TEXT)
    return reply(400, { error: "bad_request" });
  const contact = typeof req.contact === "string" ? req.contact.trim().slice(0, MAX_CONTACT) : "";

  // Adjuntos: se validan antes de tocar los contadores.
  const shots = [];
  if (req.shots != null) {
    if (!Array.isArray(req.shots) || req.shots.length > MAX_SHOTS) return reply(400, { error: "bad_request" });
    for (const s of req.shots) {
      if (!s || typeof s.data !== "string") return reply(400, { error: "bad_request" });
      const buf = Buffer.from(s.data, "base64");
      const ext = imageKind(buf);
      if (!ext || buf.length > MAX_SHOT) return reply(400, { error: "bad_attachment" });
      shots.push({ buf, ext });
    }
  }
  let logs = null;
  if (req.logs != null) {
    if (typeof req.logs !== "string") return reply(400, { error: "bad_request" });
    try {
      let b = Buffer.from(req.logs, "base64");
      if (b.length > 2 && b[0] === 0x1f && b[1] === 0x8b) b = gunzipSync(b, { maxOutputLength: MAX_LOGS + 1 });
      if (b.length > MAX_LOGS) return reply(400, { error: "bad_attachment" });
      logs = b;
    } catch { return reply(400, { error: "bad_attachment" }); }
  }

  const ip = event.requestContext?.http?.sourceIp || "unknown";
  const ns = kind === "crash" ? "crash:" : "";   // los crashes tienen contadores propios: no gastan el cupo de sugerencias
  const cdMs = kind === "crash" ? 60 * 1000 : COOLDOWN_MS;
  const ipKey = ns + hash("ip:" + ip), iidKey = ns + hash("iid:" + req.iid);
  const now = new Date();
  const limits = await collection("feedback_limits");
  await ensureIndex(limits);

  // Enfriamiento: se reserva el turno de forma atómica (si dos pedidos llegan juntos, uno solo pasa).
  for (const key of [iidKey, ipKey]) {
    const r = await limits.findOneAndUpdate(
      { _id: "cd:" + key, until: { $lte: now } },
      { $set: { until: new Date(now.getTime() + cdMs), exp: new Date(now.getTime() + cdMs) } },
      { returnDocument: "after" });
    if (!r) {
      try {
        await limits.insertOne({ _id: "cd:" + key, until: new Date(now.getTime() + cdMs), exp: new Date(now.getTime() + cdMs) });
      } catch {
        const cur = await limits.findOne({ _id: "cd:" + key });
        return reply(429, { error: "rate_limited", retry_after: Math.max(1, Math.ceil(((cur?.until || now) - now) / 1000)) });
      }
    }
  }
  // Topes diarios (por IP y globales).
  const day = now.toISOString().slice(0, 10);
  const exp = new Date(now.getTime() + 2 * 86400000);
  const bump = async (id) => (await limits.findOneAndUpdate({ _id: id }, { $inc: { n: 1 }, $setOnInsert: { exp } }, { upsert: true, returnDocument: "after" })).n;
  if ((await bump(`day:${day}:${ipKey}`)) > DAILY_PER_IP * (ns ? 2 : 1) || (await bump(`day:${day}:${ns}all`)) > DAILY_GLOBAL)
    return reply(429, { error: "rate_limited", retry_after: 3600 });

  const id = `${day}/${now.getTime()}-${hash(req.iid).slice(0, 8)}`;
  const keys = [];
  const put = async (name, body, type) => {
    const Key = `${id}/${name}`;
    await s3.send(new PutObjectCommand({ Bucket: BUCKET, Key, Body: body, ContentType: type, ServerSideEncryption: "AES256" }));
    keys.push(Key);
  };
  try {
    for (let i = 0; i < shots.length; i++) await put(`captura-${i + 1}.${shots[i].ext}`, shots[i].buf, shots[i].ext === "png" ? "image/png" : "image/jpeg");
    if (logs) await put("riven-stock.log", logs, "text/plain; charset=utf-8");
  } catch (e) {
    console.error("S3", e);
    return reply(502, { error: "storage_error" });
  }
  await (await collection("feedback")).insertOne({
    _id: id, kind, text, contact: contact || null, iid: req.iid, v: VER.test(req.v || "") ? req.v : null,
    files: keys, created: now, status: "new",
  });
  return reply(200, { ok: true });
};
