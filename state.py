"""Fuente única de los contratos: los propios y los ajenos que la app conoce.

Todo cambio (precio, republicar, cerrar, crear) pasa por acá, y acá se propaga a los caches de órdenes.
Así la tabla, la alerta y el detalle leen lo mismo y no hay que acordarse de tocar cada copia."""


def slim_to_raw(o, weapon):
    """Contrato mínimo (formato crudo de la API) a partir de un `slim`, para abrir su resumen."""
    return {"id": o["id"], "buyout_price": o["p"], "created": o.get("c"), "updated": o.get("c"),
            "item": {"weapon_url_name": weapon, "name": o.get("n") or "", "re_rolls": o["r"], "mod_rank": o.get("k"),
                     "mastery_level": o.get("m"),
                     "attributes": [{"url_name": s, "value": v, "positive": p} for s, v, p in o["s"]]},
            "owner": {"ingame_name": o.get("nm") or "?", "status": o.get("st"), "last_seen": o.get("ls")}}


class Book:
    def __init__(self, cache):
        self.cache = cache   # orders.OrderCache: persistencia y vencimiento por arma
        self.own = {}        # id -> contrato propio (último leído o escrito)
        self.others = {}     # id -> contrato ajeno visto (mercado, comparables, alertas)

    # ---- lectura ----
    def get(self, auction_id):
        """Un contrato propio o ajeno; si no está en memoria, se reconstruye desde el caché en disco."""
        a = self.own.get(auction_id) or self.others.get(auction_id)
        if a:
            return a
        hit = self.cache.find(auction_id)
        if hit:
            self.others[auction_id] = a = slim_to_raw(*hit)
        return a

    # ---- altas ----
    def own_fetched(self, auctions):
        """La API devolvió la lista completa de mis contratos: reemplaza lo que había."""
        self.own = {a["id"]: a for a in auctions}

    def put_own(self, a):
        self.own[a["id"]] = a

    def put_other(self, a, replace=True):
        if replace or a["id"] not in self.others:
            self.others[a["id"]] = a

    # ---- eventos ----
    def own_updated(self, new):
        """Cambió un contrato propio (precio, nota, visibilidad): el precio llega a todas las copias."""
        self.own[new["id"]] = new
        price = int(new["buyout_price"])
        self.cache.patch_price(new["id"], price)
        m = self.others.get(new["id"])
        if m:
            m["buyout_price"] = m["starting_price"] = price

    def created(self, new):
        """Contrato propio nuevo (publicado o republicado). El arma se vuelve a pedir: ahora lo incluye."""
        self.own[new["id"]] = new
        self.others.pop(new["id"], None)
        self.cache.forget(new["id"], new["item"]["weapon_url_name"])

    def closed(self, auction_id, weapon=None):
        """Un contrato propio se cerró o se republicó (id viejo): sale de todas las copias."""
        self.own.pop(auction_id, None)
        self.others.pop(auction_id, None)
        self.cache.forget(auction_id, weapon)
