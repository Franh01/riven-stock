// node --test src/history.test.js  (lógica de la franja no vista por polaridad)
const test = require("node:test");
const assert = require("node:assert");
const { unseen } = require("./history");

test("franja no vista por polaridad", () => {
  const gaps = { madurai: { lo: 200, hi: 1500 }, vazarin: { lo: 1, hi: 0 }, naramon: { lo: 300, hi: 1500 } };
  assert.equal(unseen(250, "madurai", gaps), true);    // dentro de la franja de madurai
  assert.equal(unseen(150, "madurai", gaps), false);   // debajo del techo: se vio, si falta es venta
  assert.equal(unseen(2000, "madurai", gaps), false);  // entre las caras
  assert.equal(unseen(250, "naramon", gaps), false);
  assert.equal(unseen(900, "vazarin", gaps), false);   // vazarin no cortó: se vio entera
  assert.equal(unseen(250, undefined, gaps), true);    // sin polaridad: alcanza con una franja
  assert.equal(unseen(150, null, gaps), false);
});
