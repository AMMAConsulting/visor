"""
Aplica la estructura de capas editada en el Excel (datos/estructura.json, ver estructura_desde_excel.py)
a las capas base de 03_construir_capas.py (datos/build/base/) y escribe el visor en web/data/:
catalogo.json y un GeoJSON por subcapa.

Los elementos nuevos de una capa base repartida entre varias subcapas no tienen sitio en el árbol: no se
publican y se listan en datos/estructura_sin_asignar.md para colocarlos en el Excel.
"""

import glob, json, os, shutil
from collections import defaultdict

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.join(RAIZ, "datos", "build", "base")
OUT = os.path.join(RAIZ, "web", "data")
EST = json.load(open(os.path.join(RAIZ, "datos", "estructura.json"), encoding="utf8"))
F_WEB = "turismo.marbella.es"

cat = json.load(open(os.path.join(BASE, "catalogo.json"), encoding="utf8"))
base_sub = {s["id"]: s for g in cat["grupos"] for s in g["subcapas"]}
base_grp = {s["id"]: g for g in cat["grupos"] for s in g["subcapas"]}
feats = {sid: json.load(open(os.path.join(BASE, sid + ".geojson"), encoding="utf8"))["features"] for sid in base_sub}

for f in glob.glob(os.path.join(OUT, "*.geojson")):
    os.remove(f)
shutil.copyfile(os.path.join(BASE, "termino.geojson"), os.path.join(OUT, "termino.geojson"))


def unicos(xs):
    return list(dict.fromkeys(x for x in xs if x))


asignados = defaultdict(set)
grupos = []
for capa in EST["capas"]:
    subs = []
    for s in capa["subcapas"]:
        fs, vistos = [], set()
        for d in s["de"]:
            ids = None if d.get("todos") else set(d["ids"])
            for f in feats.get(d["capa"], []):
                if (ids is None or f["id"] in ids) and f["id"] not in vistos:
                    fs.append(f)
                    vistos.add(f["id"])
            asignados[d["capa"]].update(f["id"] for f in feats.get(d["capa"], []) if ids is None or f["id"] in ids)
        for k, n in enumerate(s["nuevos"], 1):
            props = {k2: v for k2, v in n.items() if k2 != "coord" and v}
            fs.append({"type": "Feature", "id": "amma-%s-%d" % (s["id"], k), "properties": props,
                       "geometry": {"type": "Point", "coordinates": [n["coord"][1], n["coord"][0]]} if n["coord"] else None})
        if s.get("solo_termino"):
            fs = [f for f in fs if "Fuera del término" not in (f["properties"].get("aviso") or "")]
        b = base_sub.get(s["icono"]) if s["icono"] else None
        de = [base_sub[d["capa"]] for d in s["de"]]
        agrupa = not fs and any(x["padre"] == s["id"] for x in capa["subcapas"])
        subs.append({
            "id": s["id"], "titulo": s["titulo"], "icono": s["icono"],
            "n": sum(1 for f in fs if f["geometry"]), "sin_ubicacion": sum(1 for f in fs if not f["geometry"]),
            "geometria": b["geometria"] if b else "punto",
            "fuente": "; ".join(unicos(x.strip() for d2 in de for x in d2["fuente"].split(";"))
                                + (["AMMA Consulting"] if s["nuevos"] else [])) or None,
            "descripcion": s["descripcion"] or (b["descripcion"] if b else ""),
            # las subcapas que llevaban el color de su capa toman el de la capa nueva
            "color": b["color"] if b and b["color"] != base_grp[b["id"]]["color"] else capa["color"],
            "pendiente": s.get("pendiente"), "visible": bool(b and b["id"] == s["id"] and b["visible"]),
            "web": unicos(w for d2 in de for w in (d2["web"] or [])) or None,
            "n_web": sum(1 for f in fs if F_WEB in (f["properties"].get("fuente") or "")),
            "padre": s["padre"], "complementaria": s["complementaria"], "agrupa": agrupa})
        if not agrupa:
            json.dump({"type": "FeatureCollection", "features": fs}, open(os.path.join(OUT, s["id"] + ".geojson"), "w",
                      encoding="utf8"), ensure_ascii=False, separators=(",", ":"))
    # las subcapas que agrupan otras suman sus cifras
    for s in subs:
        if s["agrupa"]:
            hijas = [h for h in subs if h["padre"] == s["id"]]
            for k in ("n", "sin_ubicacion", "n_web"):
                s[k] = sum(h[k] for h in hijas)
            s["geometria"] = hijas[0]["geometria"]
    grupos.append({"id": capa["id"], "titulo": capa["titulo"], "color": capa["color"],
                   "descripcion": capa["descripcion"] or "", "web": capa["web"], "subcapas": subs})

json.dump({"generado": cat["generado"], "grupos": grupos}, open(os.path.join(OUT, "catalogo.json"), "w",
          encoding="utf8"), ensure_ascii=False, indent=1)

# Elementos nuevos de las capas base repartidas que no tienen sitio en el árbol
sin = []
for sid, ids in asignados.items():
    if any(d.get("todos") and d["capa"] == sid for c in EST["capas"] for s in c["subcapas"] for d in s["de"]):
        continue
    quitados = set(EST["excluidos"].get(sid, []))
    sin += [(sid, f) for f in feats[sid] if f["id"] not in ids and f["id"] not in quitados]
with open(os.path.join(RAIZ, "datos", "estructura_sin_asignar.md"), "w", encoding="utf8") as fh:
    fh.write("# Elementos sin sitio en la estructura\n\nElementos nuevos de capas base repartidas entre varias "
             "subcapas del Excel. No se publican hasta colocarlos en el Excel (hoja «Elementos») y volver a "
             "ejecutar estructura_desde_excel.py.\n\n")
    fh.write("\n".join("- %s · %s (%s)" % (base_sub[sid]["titulo"], f["properties"]["nombre"], f["id"]) for sid, f in sin)
             or "Ninguno.")
    fh.write("\n")
print("web/data: %d capas, %d subcapas, %d elementos · sin asignar: %d" % (
    len(grupos), sum(len(g["subcapas"]) for g in grupos),
    sum(s["n"] + s["sin_ubicacion"] for g in grupos for s in g["subcapas"] if not s["agrupa"]), len(sin)))
