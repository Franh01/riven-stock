"""Sugerencias, reportes de bugs y crashes de Api: métodos de Api (mixin), ver docs/ARQUITECTURA.md."""

import logging
import threading

import crashes
import feedback
import loophealth
import store
import updater


class FeedbackMixin:

    # ---- Sugerencias y reportes de bugs ----
    def feedback_state(self):
        with store.connect() as conn:
            return {"wait": feedback.wait_left(conn)}

    def feedback_logs(self):
        return feedback.read_log(self.LOG_FILE, loophealth.report())

    def feedback_send(self, kind, text, contact, with_logs, shots):
        logs = feedback.read_log(self.LOG_FILE, loophealth.report()) if with_logs else ""
        with store.connect() as conn:
            r = feedback.send(conn, updater.version_actual(), kind, text, contact, logs, shots)
        logging.info("feedback %s -> %s", kind, r.get("error") or "ok")
        return r

    # ---- Reporte de crashes y vuelta a la versión sana ----
    def crash_state(self):
        files = crashes.pending()
        with store.connect() as conn:
            auto = bool(store.settings(conn).get("crash_auto"))
        prev = ""
        if files:
            prev = feedback.sanitize(files[-1].read_text(encoding="utf-8", errors="replace"))[:1500]
        return {"n": len(files), "auto": auto, "preview": prev, "rollback": crashes.rollback_target()}

    def log_ui(self, msg):
        """Evento de la interfaz (abrir/cerrar paneles, etc.) al log, para diagnosticar."""
        logging.info("UI evento: %s", str(msg)[:300])
        return {"ok": True}

    def crash_ui_error(self, msg):
        """Error de JavaScript no capturado (la interfaz lo manda; se ignoran repetidos)."""
        msg = str(msg)[:3000]
        key = msg[:200]
        seen = getattr(self, "_ui_seen", set())
        if key not in seen and len(seen) < 20:
            seen.add(key)
            self._ui_seen = seen
            logging.error("Error en la interfaz: %s", msg)
            crashes.record_text("la interfaz", msg)
        return {"ok": True}

    def crash_send(self, always=False):
        files = crashes.pending()
        if not files:
            return {"ok": True}
        with store.connect() as conn:
            if always:
                store.set_setting(conn, "crash_auto", True)
            r = feedback.send_crash(conn, updater.version_actual(), files, self.LOG_FILE)
        logging.info("crash -> %s", r.get("error") or "ok")
        if r.get("ok"):
            crashes.discard()
        return r

    def crash_discard(self):
        crashes.discard()
        return {"ok": True}

    def crash_set_auto(self, value):
        with store.connect() as conn:
            store.set_setting(conn, "crash_auto", bool(value))
        return {"ok": True}

    def rollback_do(self):
        to = crashes.rollback_target()
        if not to:
            return {"error": "No hay una versión anterior sana para volver."}
        try:
            info = updater.buscar_version(to)
            if not info:
                return {"error": f"No se encontró la versión {to} en GitHub."}
            staging, nuevo = updater.preparar(info)
            updater.lanzar_aplicador(staging, nuevo)
        except Exception as e:
            return {"error": str(e)}
        threading.Timer(1.0, lambda: self._window.destroy()).start()
        return {"ok": True}
