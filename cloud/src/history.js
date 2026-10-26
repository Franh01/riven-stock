// Historial por publicación e inferencia de ventas. Una pasada del colector = una foto del arma:
// lo que estaba activo y ya no aparece se anota como probable venta (con nivel de confianza).
const { collection } = require("./db");

const CUT = 100;                 // la búsqueda corta en 100: con tantos resultados lo caro puede haber quedado afuera
const ONLINE = ["ingame", "online"];
const MAX_GAP_H = 36;            // con huecos más largos entre fotos baja la confianza
const KEEP_GONE_S = 30 * 86400;  // las publicaciones que no fueron venta se borran solas a los 30 días

let ready;
async function ensure() {
  if (!ready) {
    ready = (async () => {
      const l = await collection("listings");
      const s = await collection("sales");
      await l.createIndex({ weapon: 1, active: 1 });
      await l.createIndex({ created: 1 });
      await l.createIndex({ gone_at: 1 }, { expireAfterSeconds: KEEP_GONE_S });
      await s.createIndex({ weapon: 1, detected_at: 1 });
      await s.createIndex({ detected_at: 1 });
      return { listings: l, sales: s, state: await collection("collector_state") };
    })();
  }
  return ready;
}

const slim = (a) => ({
  id: a.id,
  price: a.buyout_price,
  status: a.owner?.status || null,
  seller: a.owner?.ingame_name || null,
  attrs: (a.item?.attributes || []).map((x) => [x.url_name, x.value, !!x.positive]),
  rolls: a.item?.re_rolls || 0,
  name: a.item?.name || "",
  mr: a.item?.mastery_level ?? null,
  rank: a.item?.mod_rank ?? null,
  created: a.created || null,
  pol: a.item?.polarity || null,
});

// Firma de los atributos (sin valores): sirve para detectar la misma publicación republicada.
const sig = (attrs) => attrs.map((a) => `${a[0]}${a[2] ? "+" : "-"}`).sort().join("|");

// `gaps`: franja no vista {lo, hi} por polaridad ({madurai: {...}, ...}); null si se vio todo o se usa el corte simple.
// Sin polaridad conocida (publicaciones guardadas antes de tenerla) cuenta como no vista si cae en la franja de cualquiera.
function unseen(price, pol, gaps) {
  const inGap = (g) => price >= g.lo && price <= g.hi;
  return gaps[pol] ? inGap(gaps[pol]) : Object.values(gaps).some(inGap);
}

async function record(weapon, auctions, now = new Date(), gaps = null) {
  const { listings, sales, state } = await ensure();
  const market = auctions
    .filter((a) => a.is_direct_sell && a.visible !== false && !a.closed && !a.private)
    .map(slim);
  const cur = new Map(market.map((a) => [a.id, a]));
  const truncated = !gaps && auctions.length >= CUT;
  const top = market.reduce((m, a) => Math.max(m, a.price), 0);

  const last = await state.findOne({ _id: weapon });
  const gapH = last ? (now - last.at) / 3600000 : null;
  const prev = new Map((await listings.find({ weapon, active: true }).toArray()).map((d) => [d._id, d]));
  const curSigs = new Set(market.map((a) => `${a.seller}#${a.name}#${sig(a.attrs)}`));

  const ops = [];
  const saleOps = [];
  let sold = 0;
  if (last) {   // sin foto previa no hay con qué comparar
    for (const [id, r] of prev) {
      if (cur.has(id)) continue;
      if (truncated && r.price_last >= top) continue;   // pudo quedar fuera del corte
      if (gaps && unseen(r.price_last, r.pol, gaps)) continue;   // cayó en la franja no vista de su polaridad
      const gone = { $set: { active: false, gone_at: now } };
      if (curSigs.has(`${r.seller}#${r.name}#${sig(r.attrs)}`)) {   // republicada: no es venta
        ops.push({ updateOne: { filter: { _id: id }, update: gone } });
        continue;
      }
      const online = ONLINE.includes(r.status_last);
      const fresh = (gapH ?? 0) <= MAX_GAP_H;
      const confidence = online && fresh ? "alta" : online || fresh ? "media" : "baja";
      const from = r.created ? new Date(r.created) : r.first_seen;
      saleOps.push({
        updateOne: {
          filter: { _id: id },
          update: {
            $setOnInsert: {
              weapon, detected_at: now, price: r.price_last, price_first: r.price_first,
              days_listed: Math.round(((now - from) / 86400000) * 100) / 100,
              attrs: r.attrs, rolls: r.rolls, mr: r.mr, rank: r.rank, seller: r.seller,
              confidence, gap_h: gapH == null ? null : Math.round(gapH * 100) / 100,
            },
          },
          upsert: true,
        },
      });
      ops.push({ updateOne: { filter: { _id: id }, update: gone } });
      sold++;
    }
  }
  for (const a of market) {
    if (prev.has(a.id)) {
      // Solo se escribe lo que cambió: el plan gratis de Atlas limita a ~100 operaciones por segundo.
      const r = prev.get(a.id);
      if (r.price_last !== a.price || r.status_last !== a.status || r.pol === undefined) {   // pol: completa las guardadas sin polaridad
        ops.push({ updateOne: { filter: { _id: a.id }, update: { $set: { last_seen: now, price_last: a.price, status_last: a.status, pol: a.pol } } } });
      }
    } else {
      ops.push({
        updateOne: {
          filter: { _id: a.id },
          update: {
            $setOnInsert: { weapon, name: a.name, attrs: a.attrs, rolls: a.rolls, mr: a.mr, rank: a.rank, seller: a.seller, pol: a.pol, created: a.created, first_seen: now, price_first: a.price },
            $set: { last_seen: now, price_last: a.price, status_last: a.status, active: true },
            $unset: { gone_at: "" },
          },
          upsert: true,
        },
      });
    }
  }
  if (saleOps.length) await sales.bulkWrite(saleOps, { ordered: false });
  if (ops.length) await listings.bulkWrite(ops, { ordered: false });
  await state.updateOne({ _id: weapon }, { $set: { at: now, n: market.length, truncated: truncated || !!gaps } }, { upsert: true });
  return sold;
}

module.exports = { record, ensure, unseen };
