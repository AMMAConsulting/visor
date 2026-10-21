"""
Lee el recorte de Marbella (build/marbella.osm.pbf) y guarda en build/osm.pkl:
  - el término municipal (polígono),
  - todos los elementos con etiquetas (puntos, líneas y áreas) dentro del término,
  - las rutas (GR 249, Senda Litoral, EuroVelo 8...) como líneas recortadas al término.

Uso: python 02_leer_osm.py
"""

import os, pickle
import osmium
from shapely import wkb
from shapely.geometry import MultiLineString, Point
from shapely.ops import linemerge

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PBF = os.path.join(BASE, "build", "marbella.osm.pbf")
SALIDA = os.path.join(BASE, "build", "osm.pkl")
fab = osmium.geom.WKBFactory()

AREA_SI = {"leisure", "natural", "landuse", "amenity", "tourism", "historic", "shop", "building", "boundary",
           "harbour", "golf", "place", "water", "sport"}

termino, elementos, lineas_via, rutas = None, [], {}, []

# 1) áreas (cerradas y multipolígonos) y nodos/vías sueltas
for o in osmium.FileProcessor(PBF).with_locations().with_areas():
    t = dict(o.tags)
    if not t:
        continue
    try:
        if o.is_area():
            if t.get("boundary") == "administrative" and t.get("name") == "Marbella" and t.get("admin_level") == "8":
                termino = wkb.loads(fab.create_multipolygon(o), hex=True)
                continue
            if not any(k in t for k in AREA_SI):
                continue
            g = wkb.loads(fab.create_multipolygon(o), hex=True)
            elementos.append({"id": ("w" if o.from_way() else "r") + str(o.orig_id()), "t": t, "g": g})
        elif o.is_node():
            g = Point(o.location.lon, o.location.lat)
            elementos.append({"id": "n" + str(o.id), "t": t, "g": g})
        elif o.is_way():
            g = wkb.loads(fab.create_linestring(o), hex=True)
            lineas_via[o.id] = g
            if not o.is_closed() or t.get("highway") or t.get("route"):
                elementos.append({"id": "w" + str(o.id), "t": t, "g": g})
        elif o.is_relation() and t.get("type") == "route":
            rutas.append({"id": "r" + str(o.id), "t": t, "miembros": [m.ref for m in o.members if m.type == "w"]})
    except Exception:
        pass

assert termino is not None, "No se ha encontrado el término municipal de Marbella"

# 2) rutas: unir sus vías y recortar al término
for r in rutas:
    partes = [lineas_via[w] for w in r["miembros"] if w in lineas_via]
    if not partes:
        continue
    g = linemerge(MultiLineString(partes)).intersection(termino.buffer(0.002))
    if not g.is_empty:
        elementos.append({"id": r["id"], "t": r["t"], "g": g})

dentro = [e for e in elementos if e["g"].intersects(termino)]
pickle.dump({"termino": termino, "elementos": dentro}, open(SALIDA, "wb"))
print(f"Término: {termino.area * 1e4:.0f} (grados² x1e4); elementos dentro: {len(dentro)}; rutas: {len(rutas)}")
