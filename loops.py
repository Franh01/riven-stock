"""Bucles de fondo de Api (contador, fotos, oportunidades): métodos de Api (mixin), ver docs/ARQUITECTURA.md."""

import json
import logging
import time
from datetime import datetime, timezone

import loophealth
import opportunities
import store
from ratelimit import QUEUE


class LoopsMixin:

    TICK_S = 60          # una muestra por minuto
    TICK_CAP_S = 120     # tope por muestra: una suspensión de la PC no suma horas
    STATUS_REFRESH_S = 300
    RENEW_BEFORE_S = 600

    def _counter_loop(self):
        last = time.monotonic()
        st, st_at = None, 0.0
        while not self._stop.wait(self.TICK_S):
            now = time.monotonic()
            elapsed = min(now - last, self.TICK_CAP_S)
            last = now
            try:
                if st is None or now - st_at > self.STATUS_REFRESH_S:
                    st, st_at = self.client.get_status(), now
                until = st.get("statusUntil") if st else None
                left = (datetime.fromisoformat(until.replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds() if until else 0
                self._online = bool(st and st.get("status") in ("online", "ingame") and left > 0)
                if self._online:
                    with store.connect() as conn:
                        store.add_online_seconds(conn, elapsed)
                        # solo cuentan los rivens visibles: uno oculto no está a la venta
                        store.add_riven_seconds(conn, [i for i, a in list(self._seen.items()) if a.get("visible", True)], elapsed)
                    if left < self.RENEW_BEFORE_S:   # el servidor corta a las 4 h: renovar mientras la app esté abierta
                        st, st_at = self.client.set_status(st["status"], 240 * 60), now
                loophealth.beat("contador", self.TICK_S)
            except Exception as e:
                loophealth.beat("contador", self.TICK_S, e)
                st = None   # sin red o error de la API: no suma ese minuto y reintenta

    SNAPSHOT_PASS_S = 120

    def _snapshot_loop(self):
        """Una foto diaria por arma (stock y favoritas), solo en idle y por la cola central."""
        while not self._stop.wait(self.SNAPSHOT_PASS_S):
            loophealth.beat("fotos", self.SNAPSHOT_PASS_S)
            if not self._cache.idle() or QUEUE.busy():
                continue
            try:
                with store.connect() as conn:
                    tracked = store.settings(conn).get("tracked_weapons") or []
                    todo = [w for w in list(self._wanted_weapons()) + tracked if not store.snapshot_done_today(conn, w)]
                    if not todo:
                        continue
                    e = self._cache.get(todo[0], self.VIEW_MAX_AGE_S) or self._cache.load(todo[0])
                    store.save_snapshot(conn, todo[0], e.get("market", []))
            except Exception as e:
                loophealth.beat("fotos", self.SNAPSHOT_PASS_S, e)
                self._stop.wait(60)

    OPP_PASS_S = 90

    def _opp_loop(self):
        """Mira el caché de las armas vigiladas (lo llena el caché en idle) y avisa de las publicaciones
        muy por debajo de su estimado. No hace pedidos propios."""
        while not self._stop.wait(self.OPP_PASS_S):
            loophealth.beat("oportunidades", self.OPP_PASS_S)
            try:
                with store.connect() as conn:
                    cfg = store.settings(conn)
                if not cfg.get("opp_enabled"):
                    continue
                self.scan_opportunities(cfg)
            except Exception as e:
                loophealth.beat("oportunidades", self.OPP_PASS_S, e)
                logging.info("Alertas de oportunidad: se reintenta", exc_info=True)

    def scan_opportunities(self, cfg=None):
        if cfg is None:
            with store.connect() as conn:
                cfg = store.settings(conn)
        thr, gain = cfg.get("opp_threshold", 30), cfg.get("opp_min_gain", 15)
        mine = set(self._seen)
        n_new = 0
        for w in cfg.get("opp_weapons") or []:
            e = self._cache.get(w, self.CACHE_MAX_AGE_S)
            if not e or not e.get("market"):
                continue
            for o in opportunities.find(e["market"], self._rtype(w), thr, gain, mine, weapon=w):
                text = json.dumps({"weapon": w, **o}, ensure_ascii=False)
                with store.connect() as conn:
                    if store.add_opportunity(conn, o["id"], text):
                        n_new += 1
        return n_new
