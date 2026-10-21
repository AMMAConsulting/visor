"""
Recorta el extracto de Andalucía de OpenStreetMap (Geofabrik) a la zona de Marbella, con
referencias completas (las vías llevan todos sus nodos y las relaciones todos sus miembros),
para poder montar después áreas y rutas sin cargar toda Andalucía en memoria.

Uso: python 01_recortar_osm.py   (lee build/andalucia.osm.pbf y escribe build/marbella.osm.pbf)
"""

import os
import osmium

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGEN = os.path.join(BASE, "build", "andalucia.osm.pbf")
DESTINO = os.path.join(BASE, "build", "marbella.osm.pbf")
S, W, N, E = 36.46, -5.03, 36.62, -4.74          # término municipal con margen

# rutas lineales que interesan aunque salgan del término (se recortan después)
RUTAS = ("GR 249", "GR-249", "GR249", "EuroVelo 8", "EV8", "Senda Litoral")


def dentro(loc):
    return loc.valid() and S <= loc.lat <= N and W <= loc.lon <= E


def ruta_interesante(tags):
    texto = " ".join(tags.get(k, "") for k in ("name", "ref", "network", "route"))
    return tags.get("type") == "route" and any(r.lower() in texto.lower() for r in RUTAS)


vias = set()
with osmium.BackReferenceWriter(DESTINO, ref_src=ORIGEN, overwrite=True) as w:
    for o in osmium.FileProcessor(ORIGEN).with_locations():
        if o.is_node():
            if dentro(o.location) and len(o.tags):
                w.add_node(o)
        elif o.is_way():
            if any(dentro(n.location) for n in o.nodes):
                w.add_way(o)
                vias.add(o.id)
        elif o.is_relation():
            t = dict(o.tags)
            if ruta_interesante(t) or (t.get("boundary") == "administrative" and t.get("name") == "Marbella"):
                w.add_relation(o)
            elif t.get("type") in ("multipolygon", "route") and any(
                    m.type == "w" and m.ref in vias for m in o.members):
                w.add_relation(o)

print(f"Recorte escrito en {DESTINO} ({os.path.getsize(DESTINO) / 1e6:.1f} MB)")
