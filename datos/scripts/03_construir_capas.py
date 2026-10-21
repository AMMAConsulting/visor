"""
Construye las capas y subcapas del Visor a partir de:
  - web_turismo.json               (directorio de recursos de turismo.marbella.es, 00b_descargar_web.py)
  - build/osm.pkl                  (OpenStreetMap, 02_leer_osm.py)
  - rta_marbella_no_vut.json       (Registro de Turismo de Andalucía, OpenRTA)
  - distinciones.json              (Guía MICHELIN y Guía Repsol, edición 2026)

El árbol sigue el de la web de turismo: una capa por sección y una subcapa por categoría, con los
mismos nombres y en el mismo orden. Cada recurso de la web se une con su entidad de OSM o del RTA
cuando la hay (para aprovechar su geometría y sus atributos); si no, entra como punto con las
coordenadas que publica la web. Detrás de las categorías de la web van las subcapas complementarias.
Ningún recurso de la web se queda fuera: los que no caen en ninguna subcapa van a una de control y
se listan en cobertura_web.md.

Escribe en ../web/data/ un GeoJSON por subcapa y catalogo.json con la estructura de capas,
que lee el visor y del que salen también las tablas del documento Word.

Uso: python 03_construir_capas.py
"""

import copy, json, os, pickle, re, time, unicodedata, urllib.parse, urllib.request
from datetime import date
from difflib import SequenceMatcher
from pyproj import Transformer
from shapely.geometry import Point, mapping, shape
from shapely.ops import unary_union

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(os.path.dirname(BASE), "web")
OUT = os.path.join(WEB, "data")
os.makedirs(OUT, exist_ok=True)

osm = pickle.load(open(os.path.join(BASE, "build", "osm.pkl"), "rb"))
TERMINO, E = osm["termino"], osm["elementos"]
RTA = json.load(open(os.path.join(BASE, "rta_marbella_no_vut.json"), encoding="utf8"))
DIST = json.load(open(os.path.join(BASE, "distinciones.json"), encoding="utf8"))
WEBR = json.load(open(os.path.join(BASE, "web_turismo.json"), encoding="utf8"))["recursos"]
utm = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)

F_OSM = "OpenStreetMap (ODbL)"
F_RTA = "Registro de Turismo de Andalucía (OpenRTA)"
F_WEB = "turismo.marbella.es"
URL_WEB = "https://turismo.marbella.es"
for i, r in enumerate(WEBR):
    r["i"] = i


def norm(s):
    s = re.sub(r"[´'’`]", "", str(s or ""))
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def T(e, k):
    return e["t"].get(k, "")


def nombre(e):
    return T(e, "name") or T(e, "name:es")


# -- utilidades de geometría ------------------------------------------------------------------
PLAYAS_POL = unary_union([e["g"] for e in E if T(e, "natural") == "beach" and e["g"].geom_type != "Point"])
PLAYAS_BUF = PLAYAS_POL.buffer(0.00012)         # ~12 m: sobre la arena o en su borde


def cerca_playa(e):
    return e["g"].intersects(PLAYAS_BUF)


def redondear(geo, nd=6):
    if isinstance(geo, (list, tuple)):
        if geo and isinstance(geo[0], (int, float)):
            return [round(geo[0], nd), round(geo[1], nd)]
        return [redondear(g, nd) for g in geo]
    return geo


def geom(e, simp=0.00003):
    g = e["g"]
    if g.geom_type in ("LineString", "MultiLineString", "Polygon", "MultiPolygon", "GeometryCollection"):
        g = g.simplify(simp, preserve_topology=True)
        if g.geom_type == "GeometryCollection":
            g = unary_union([p for p in g.geoms if not p.is_empty])
    m = mapping(g)
    return {"type": m["type"], "coordinates": redondear(m["coordinates"])}


def direccion_osm(t):
    calle, num = t.get("addr:street", ""), t.get("addr:housenumber", "")
    return f"{calle} {num}".strip()


COCINAS = {"italian": "italiana", "spanish": "española", "mediterranean": "mediterránea", "seafood": "marisco",
           "fish": "pescado", "japanese": "japonesa", "chinese": "china", "indian": "india", "burger": "hamburguesas",
           "steak_house": "asador", "mexican": "mexicana", "french": "francesa", "thai": "tailandesa",
           "asian": "asiática", "international": "internacional", "argentinian": "argentina", "lebanese": "libanesa",
           "greek": "griega", "peruvian": "peruana", "vegetarian": "vegetariana", "vegan": "vegana",
           "american": "americana", "grill": "a la brasa", "barbecue": "barbacoa", "british": "británica",
           "russian": "rusa", "turkish": "turca", "moroccan": "marroquí", "fusion": "fusión", "andalusian": "andaluza",
           "coffee_shop": "cafetería", "ice_cream": "heladería", "breakfast": "desayunos", "healthy": "saludable",
           "chicken": "pollo", "sandwich": "bocadillos", "crepe": "crepes", "middle_eastern": "de Oriente Medio",
           "german": "alemana", "belgian": "belga", "scandinavian": "escandinava", "irish": "irlandesa",
           "dutch": "neerlandesa", "korean": "coreana", "vietnamese": "vietnamita", "regional": "regional",
           "tapas": "tapas", "pizza": "pizza", "sushi": "sushi", "kebab": "kebab", "local": "local",
           "nikkei": "nikkei", "brunch": "brunch", "paella": "paella", "swedish": "sueca", "danish": "danesa",
           "portuguese": "portuguesa", "brazilian": "brasileña", "cuban": "cubana", "venezuelan": "venezolana",
           "basque": "vasca", "galician": "gallega", "catalan": "catalana", "noodle": "fideos", "ramen": "ramen",
           "dessert": "postres", "cake": "tartas", "pasta": "pasta", "wine": "vinos", "bar&grill": "bar y parrilla"}


def cocina(t):
    vs = [v.strip().lower() for v in t.get("cuisine", "").split(";") if v.strip()]
    return ", ".join(COCINAS.get(v, v.replace("_", " ")) for v in vs)


def props_osm(e, **extra):
    t = e["t"]
    p = {"nombre": nombre(e), "direccion": direccion_osm(t), "web": t.get("website") or t.get("contact:website", ""),
         "telefono": t.get("phone") or t.get("contact:phone", ""), "horario": t.get("opening_hours", ""),
         "fuente": F_OSM, "origen": f"https://www.openstreetmap.org/{ {'n': 'node', 'w': 'way', 'r': 'relation'}[e['id'][0]]}/{e['id'][1:]}"}
    p.update(extra)
    return {k: v for k, v in p.items() if v not in ("", None)}


def punto(e):
    g = e["g"]
    if g.geom_type == "Point":
        return e
    c = g.representative_point() if g.geom_type in ("Polygon", "MultiPolygon") else g.centroid
    return {**e, "g": c}


# -- catálogo ----------------------------------------------------------------------------------
CAT, USADOS = [], set()
WEB_USADOS, WEB_PEND, AJENOS_USADOS, LOG_PARES = set(), [], set(), []


def grupo(gid, titulo, color, descripcion, web=None):
    CAT.append({"id": gid, "titulo": titulo, "color": color, "descripcion": descripcion,
                "web": URL_WEB + web + ".html" if web else None, "subcapas": []})


def sub(sid, titulo, feats, geometria, fuente, descripcion, color=None, pendiente=None, visible=False, web=None):
    """web: rutas de las páginas de la web que reproduce la subcapa (None si es complementaria)."""
    fc = {"type": "FeatureCollection", "features": feats}
    json.dump(fc, open(os.path.join(OUT, sid + ".geojson"), "w", encoding="utf8"), ensure_ascii=False,
              separators=(",", ":"))
    n_web = len({i for i in WEB_PEND})
    WEB_USADOS.update(WEB_PEND)
    CAT[-1]["subcapas"].append({
        "id": sid, "titulo": titulo, "n": sum(1 for f in feats if f["geometry"]),
        "sin_ubicacion": sum(1 for f in feats if not f["geometry"]), "geometria": geometria,
        "fuente": fuente, "descripcion": descripcion, "color": color or CAT[-1]["color"],
        "pendiente": pendiente, "visible": visible,
        "web": [URL_WEB + w + ".html" for w in web] if web else None, "n_web": n_web})
    ASIGNACION[sid] = list(WEB_PEND)
    WEB_PEND.clear()
    print(f"  {sid:28s} {len(feats):5d}  (web {n_web})")


ASIGNACION = {}


def feat(e, props, como_punto=False):
    e2 = punto(e) if como_punto else e
    return {"type": "Feature", "id": e["id"], "properties": props, "geometry": geom(e2)}


def osm_sel(cond, excluir_usados=True, con_nombre=True):
    xs = []
    for e in E:
        if excluir_usados and e["id"] in USADOS:
            continue
        if con_nombre and not nombre(e):
            continue
        if cond(e):
            xs.append(e)
    return xs


def marcar(xs):
    for e in xs:
        USADOS.add(e["id"])
    return xs


def dedup(xs, dist=0.0004):
    """Quita duplicados (mismo nombre a menos de ~40 m: nodo + edificio, por ejemplo)."""
    vistos, res = [], []
    for e in sorted(xs, key=lambda e: e["id"][0] != "n"):
        c, n = punto(e)["g"], norm(nombre(e))
        if any(n == n2 and c.distance(c2) < dist for n2, c2 in vistos):
            USADOS.add(e["id"])
            continue
        vistos.append((n, c))
        res.append(e)
    return res


# -- RTA ----------------------------------------------------------------------------------------
def num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


CACHE_GEO = os.path.join(BASE, "geocodificacion.json")
cache_geo = json.load(open(CACHE_GEO, encoding="utf8")) if os.path.exists(CACHE_GEO) else {}


def cartociudad(direccion, municipio="Marbella"):
    clave = direccion if municipio == "Marbella" else f"{direccion} | {municipio or '-'}"
    if clave in cache_geo:
        return cache_geo[clave]
    q = urllib.parse.quote(direccion + (", " + municipio if municipio else ""))
    try:
        r = json.loads(urllib.request.urlopen(
            f"https://www.cartociudad.es/geocoder/api/geocoder/find?q={q}", timeout=30).read())
        ok = r.get("lat") and (not municipio or r.get("muni", "").lower() == municipio.lower())
        res = [r["lng"], r["lat"]] if ok else None
    except Exception:
        res = None
    cache_geo[clave] = res
    time.sleep(0.3)
    return res


def limpia_dir(d):
    d = re.split(r"\s+(Blq\.|Portal|Esc\.|Plta/Piso|Pta/Letra|Compl\.Dom\.|Calif\.)", d or "")[0]
    d = re.sub(r"^(CALLE|AVENIDA|PLAYA|URBANIZACION|CARRETERA|CONJUNTO|LUGAR|PLAZA)\s+(?=\1)", "", d.strip())
    return d.replace(" Nº ", " ").strip()


MARINA = next(punto(e)["g"] for e in E if "virgen del carmen" in norm(nombre(e)))


def rta_feat(r, extra=None):
    x, y = num(r.get("coord_x")), num(r.get("coord_y"))
    aprox = False
    if x and y:
        lon, lat = utm.transform(x, y)
    elif "PUERTO DEPORTIVO DE MARBELLA" in (r.get("establishment_address") or "").upper():
        lon, lat, aprox = MARINA.x, MARINA.y, True
    else:
        ll = cartociudad(limpia_dir(r.get("establishment_address")))
        if not ll:
            return None
        (lon, lat), aprox = ll, True
    if not TERMINO.buffer(0.01).contains(Point(lon, lat)):
        return None
    p = {"nombre": (r.get("name") or "").title() or r["objects_type_id"], "categoria": " · ".join(
        v for v in (r.get("group"), r.get("categories")) if v and v != "Única"),
         "direccion": (r.get("establishment_address") or "").title(), "registro": r.get("registration_code"),
         "plazas": r.get("tot_gen_places"), "unidades": r.get("tot_gen_ua"), "web": r.get("url") or "",
         "fuente": F_RTA}
    if aprox:
        p["aviso"] = "Ubicación aproximada, obtenida a partir de la dirección"
    p.update(extra or {})
    p = {k: v for k, v in p.items() if v not in ("", None, "-", "No disponible")}
    return {"type": "Feature", "id": f"rta{r['id']}", "properties": p,
            "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]}}


def rta(cond, extra=None):
    return [f for f in (rta_feat(r, extra) for r in RTA if cond(r)) if f]


# -- recursos de la web ---------------------------------------------------------------------------
def web(*rutas, excepto=()):
    """Recursos publicados en esas páginas de la web o en las que cuelgan de ellas."""
    dentro = lambda p, xs: any(p == x or p.startswith(x + "/") for x in xs)
    return [r for r in WEBR if dentro(r["pagina"][:-5], rutas) and not dentro(r["pagina"][:-5], excepto)]


VACIAS = set("de del la las el los y e en a al the and hotel hoteles club restaurante restaurant bar beach playa "
             "marbella puerto san pedro alcantara parking aparcamiento golf spa centro c cc".split())


def titulo_web(r):
    return re.sub(r"\s*\*+\s*$", "", r["titulo"]).strip()


# palabras que comparten muchos sitios distintos (barrios, tipos de local): no bastan para emparejar
LUGARES = set("banus andalucia elviria guadalmina miraflores cabopino monteros nagueles casa iglesia parroquia ermita "
              "capilla plaza parque villa villas clinica clinic sport sports gallery galeria burger cafe grill lounge "
              "shop bike bikes boat boats car cars rent apartments apartamentos suites resort medical comercial mercado "
              "mercadillo municipal escuela academia school tenis padel gym gimnasio nueva costa sol sky hospital salud".split())


def palabras(t, sin_lugares=True):
    return {w for w in norm(t).split() if w not in VACIAS and not (sin_lugares and w in LUGARES) and len(w) > 1}


def _igual(x, y):
    return x == y or (min(len(x), len(y)) >= 5 and SequenceMatcher(None, x, y).ratio() >= 0.85)


def parecido(a, b):
    """0–1. Para entidades de la misma clase: basta una palabra distintiva en común."""
    na, nb = " ".join(norm(a).split()), " ".join(norm(b).split())
    if na and nb and min(len(na), len(nb)) >= 4 and (na == nb or f" {na} " in f" {nb} " or f" {nb} " in f" {na} "):
        return 1.0
    ca, cb = na.replace(" ", ""), nb.replace(" ", "")
    if min(len(ca), len(cb)) >= 5 and SequenceMatcher(None, ca, cb).ratio() >= 0.88:   # Sunbikes / Sun Bikes
        return 0.95
    A, B = palabras(a), palabras(b)
    if not A or not B:
        return 0.0
    return sum(1 for x in A if any(_igual(x, y) for y in B)) / min(len(A), len(B))


def casi_igual(a, b):
    """Para entidades de otra clase: el nombre ha de ser prácticamente el mismo."""
    na, nb = norm(a).replace(" ", ""), norm(b).replace(" ", "")
    if min(len(na), len(nb)) < 4:
        return na == nb
    if (na in nb or nb in na) and min(len(na), len(nb)) / max(len(na), len(nb)) >= 0.6:
        return True
    A, B = palabras(a, False), palabras(b, False)
    comunes = sum(1 for x in A if any(_igual(x, y) for y in B))
    return SequenceMatcher(None, na, nb).ratio() >= 0.92 or (bool(A and B) and comunes / max(len(A), len(B)) >= 0.75)


GENERICO = re.compile(r"\(sin nombre en origen\)|^parada de taxi$|^parque canino$|^punto de recarga$", re.I)


def ref_ruta(t):
    m = re.search(r"\b(PR|SL|GR)[\s-]*A?[\s-]*(\d+)", t or "", re.I)
    return f"{m.group(1).upper()}{m.group(2)}" if m else None


def direccion_web(r):
    d = r.get("direccion") or ""
    if r.get("etiqueta") and d.startswith(r["etiqueta"]):
        d = d[len(r["etiqueta"]):]
    return d.strip(" :,") or None


OTROS_MUNICIPIOS = ["Torremolinos", "Benalmádena", "Fuengirola", "Mijas", "Estepona", "Málaga", "Ronda", "Ojén",
                    "Istán", "Benahavís", "Castellar", "Manilva", "Casares"]


def coordenadas(r):
    lat, lon = r.get("lat"), r.get("lon")
    if lat is not None and not (35.5 < lat < 37.5 and -6.5 < lon < -3.5):
        lat, lon = (lon, lat) if (35.5 < lon < 37.5 and -6.5 < lat < -3.5) else (None, None)
    return [round(lon, 6), round(lat, 6)] if lat is not None else None


# el mismo recurso puede traer coordenadas en otra categoría de la web
COORD_TITULO = {}
for r in WEBR:
    if coordenadas(r):
        COORD_TITULO.setdefault(norm(titulo_web(r)), coordenadas(r))

# lugares conocidos que las direcciones citan («Puente Romano Fase II», «junto al Hotel El Fuerte»…)
REFERENCIAS = sorted({(" ".join(norm(titulo_web(r)).split()), tuple(coordenadas(r))) for r in WEBR if coordenadas(r)} |
                     {(" ".join(norm(nombre(e)).split()), (round(punto(e)["g"].x, 6), round(punto(e)["g"].y, 6)))
                      for e in E if nombre(e) and not T(e, "highway") and e["t"].get("type") != "route"},
                     key=lambda x: -len(x[0]))
REFERENCIAS = [(n, ll) for n, ll in REFERENCIAS if len(n) >= 9 and len(n.split()) >= 2]


def candidatos_dir(d):
    """Variantes de la dirección, de la más limpia (calle y número) a la original."""
    d = re.sub(r"^(Galer[ií]a de Arte|Turoperadores|Asociaciones|Bodas(, Congresos)?|P[uú]blico, (Exterior|Interior)|"
               r"Privad[oa][^ ]*)\s+", "", d.strip())
    d = re.sub(r"\bC/\s*", "Calle ", d)
    d = re.sub(r"\bAvda?\.\s*|\bAv\.\s*|\bAvd\.\s*", "Avenida ", d)
    d = re.sub(r"\b(C\.?\s?P\.?:?\s*)?\d{5}\b", "", d)
    out = []
    m = re.search(r"((?:Calle|Avenida|Plaza|Paseo|P\.º|Urb\.?|Urbanización|Carretera|Camino)\s+[^,;]+?)"
                  r"(?:,\s*|\s+n[º°o]\.?\s*)(\d+)\b", d, re.I)
    if m:
        out.append(f"{m.group(1).strip()} {m.group(2)}")
    m = re.search(r"((?:Calle|Avenida|Plaza|Paseo|Urb\.?|Urbanización|Carretera|Camino)\s+[^,;.]+)", d, re.I)
    if m:
        out.append(m.group(1).strip())
    out.append(re.sub(r"\s+", " ", d).strip(" ,.-–"))
    return list(dict.fromkeys(x for x in out if len(x) > 5))


def ubicar(r):
    """[lon, lat] del recurso y si es aproximada; usa la dirección cuando la web no trae coordenadas."""
    ll = coordenadas(r)
    if ll:
        return ll, False
    if norm(titulo_web(r)) in COORD_TITULO:
        return COORD_TITULO[norm(titulo_web(r))], False
    d = direccion_web(r)
    if not d:
        return None, False
    muni = next((m for m in OTROS_MUNICIPIOS if norm(m) in norm(d)), "Marbella")
    if re.search(r"\d|calle|c/|avda|av\.|avenida|plaza|urb\.|paseo|carretera|camino", d, re.I):
        for q in candidatos_dir(d):
            ll = cartociudad(q, muni)
            if ll and (muni != "Marbella" or en_su_zona(d, ll)):
                return ll, True
    nd = " " + " ".join(norm(d).split()) + " "
    for n, ll in REFERENCIAS:
        if f" {n} " in nd and (muni != "Marbella" or en_su_zona(d, ll)):
            return list(ll), True
    return None, False


# longitudes de cada zona de Marbella, para descartar calles homónimas de otro barrio
ZONAS = [(r"\b2960[123]\b|marbella centro|casco antiguo", -4.935, -4.86),
         (r"\b2967[08]\b|san pedro", -5.03, -4.955),
         (r"\b29660\b|nueva andalucia|puerto banus", -4.995, -4.93),
         (r"\b29604\b|elviria|las chapas|el rosario|cabopino|calahonda", -4.86, -4.74)]


def en_su_zona(d, ll):
    for patron, oeste, este in ZONAS:
        if re.search(patron, norm(d) + " " + d):
            return oeste <= ll[0] <= este
    return True


def ficha(r):
    if r.get("articulo"):
        return f"{URL_WEB}/index.php?option=com_content&view=article&id={r['articulo']}"
    return URL_WEB + r["pagina"]


def web_feat(r, etiqueta=False, extra=None):
    ll, aprox = ubicar(r)
    p = {"nombre": titulo_web(r), "categoria": r.get("etiqueta") if etiqueta else None, "direccion": direccion_web(r),
         "imagen": r.get("imagen"), "ficha": ficha(r), "fuente": F_WEB}
    if ll is None:
        p["aviso"] = "La web no publica su ubicación"
    elif aprox:
        p["aviso"] = "Ubicación aproximada, obtenida a partir de la dirección"
    elif not TERMINO.buffer(0.002).contains(Point(ll)):
        p["aviso"] = "Fuera del término municipal de Marbella"
    p.update(extra or {})
    return {"type": "Feature", "id": f"web{r.get('articulo') or r['i']}",
            "properties": {k: v for k, v in p.items() if v not in ("", None)},
            "geometry": {"type": "Point", "coordinates": ll} if ll else None}


def vestir(f, r, etiqueta=False):
    """Pone en la entidad de OSM o del RTA el nombre, la imagen y la ficha con que la presenta la web."""
    p = f["properties"]
    p["nombre"] = titulo_web(r)
    if etiqueta and r.get("etiqueta"):
        p["categoria"] = r["etiqueta"]
    p.setdefault("direccion", direccion_web(r))
    if r.get("imagen"):
        p["imagen"] = r["imagen"]
    p["ficha"] = ficha(r)
    p["fuente"] = F_WEB + "; " + p.get("fuente", "")
    f["properties"] = {k: v for k, v in p.items() if v not in ("", None)}


def con_web(recs, propios=(), ajenos=(), radio=0.004, etiqueta=False, por_ref=False):
    """Une los recursos de la web con entidades de OSM/RTA.

    propios: entidades de la misma clase, que entran en la subcapa aunque la web no las cite.
    ajenos:  entidades de otras subcapas o descartadas, que solo entran si casan con un recurso de la web
             (se copian, de modo que un mismo sitio puede estar en varias categorías, como en la web).
    """
    unicos, vistos = [], {}
    for r in recs:
        WEB_PEND.append(r["i"])
        k = norm(titulo_web(r))
        if k in vistos:
            continue
        vistos[k] = r
        unicos.append(r)
    cands = [(f, False) for f in propios] + [(f, True) for f in ajenos]
    formas = [shape(f["geometry"]) if f["geometry"] else None for f, _ in cands]
    pares = []
    for j, r in enumerate(unicos):
        ll, _ = ubicar(r)
        pt = Point(ll) if ll else None
        for k, (f, ajeno) in enumerate(cands):
            nom = f["properties"].get("nombre", "")
            mismo_codigo = por_ref and ref_ruta(r["titulo"]) and ref_ruta(r["titulo"]) == ref_ruta(f["properties"].get("ref"))
            if mismo_codigo and formas[k] is not None:       # un sendero con el mismo código (PR-A 168, GR 249)
                d = formas[k].distance(pt) if pt else 0
                if d <= 0.08:
                    pares.append((1 - d, j, k))
                continue
            if ajeno:
                if formas[k] is None or not casi_igual(titulo_web(r), nom) or (pt and formas[k].distance(pt) > 0.002):
                    continue
                s = 1.0
            else:
                s = parecido(titulo_web(r), nom)
            # un área sin nombre en origen (una playa, por ejemplo) que contiene el punto de la web
            if s < 0.5 and pt and formas[k] is not None and GENERICO.search(nom) and formas[k].contains(pt):
                s = 0.6
            if s < 0.5 or formas[k] is None:
                continue
            d = formas[k].distance(pt) if pt else (0 if s == 1 else 1)
            if d <= radio:
                pares.append((s - d * 50, j, k))
    pares.sort(reverse=True)
    pareja, cogidos = {}, set()
    for sc, j, k in pares:
        if j not in pareja and k not in cogidos:
            pareja[j] = k
            cogidos.add(k)
            if sc < 0.99 or cands[k][1]:
                LOG_PARES.append(f"{sc:5.2f} {'otra clase' if cands[k][1] else 'misma    '} | {titulo_web(unicos[j])} | "
                                 f"{cands[k][0]['properties'].get('nombre')}")
    out = [f for f, ajeno in cands if not ajeno]
    for j, r in enumerate(unicos):
        if j in pareja:
            f, ajeno = cands[pareja[j]]
            if ajeno:
                AJENOS_USADOS.add(f["id"])
                f = copy.deepcopy(f)
                out.append(f)
            vestir(f, r, etiqueta)
        else:
            out.append(web_feat(r, etiqueta))
    return out


def sobrantes(fs):
    return [f for f in fs if f["id"] not in AJENOS_USADOS]


# ================================================================================================
print("Seleccionando entidades de OSM y del RTA...")
P = lambda xs, **kw: [feat(e, props_osm(e, **kw), True) for e in xs]          # como puntos

BANDERA = ["cabopino", "cable", "faro", "fontanilla", "nagueles", "casablanca", "monteros", "adelfas",
           "guadalmina", "san pedro", "venus", "bajadilla"]
playas = []
for e in marcar(osm_sel(lambda e: T(e, "natural") == "beach", con_nombre=False)):
    n = norm(nombre(e))
    if not n and e["g"].area < 2e-7:
        continue
    playas.append(feat(e, props_osm(e, nombre=nombre(e) or "Playa (sin nombre en origen)",
                                    bandera_azul="Sí (2026, ADEAC)" if any(b in n for b in BANDERA) else None)))
puertos = [feat(e, props_osm(e)) for e in dedup(marcar(osm_sel(
    lambda e: T(e, "leisure") == "marina" or T(e, "landuse") == "harbour" or T(e, "harbour"))))]
RE_CLUB = re.compile(r"beach club|club de playa|nikki beach|ocean club|puro beach|trocadero|la sala by the sea|"
                     r"nao pool|amare beach|playa padre|bounty beach|kova beach|amu beach", re.I)
clubes = P(marcar(dedup(osm_sel(lambda e: (RE_CLUB.search(nombre(e)) and (T(e, "amenity") or T(e, "leisure")))
                                          or (T(e, "leisure") == "beach_resort")))))
nautica = P(marcar(dedup(osm_sel(lambda e: T(e, "sport") in ("sailing", "scuba_diving", "surfing", "kitesurfing",
                                                                  "water_ski", "canoe", "diving", "windsurfing",
                                                                  "rowing", "motorboat")
                                       or T(e, "amenity") == "boat_rental" or T(e, "club") == "sailing"
                                       or T(e, "shop") in ("boat", "water_sports", "diving")
                                       or re.search(r"cableski|diving|buceo|jet ?ski|charter|paddle ?surf|sup", nombre(e), re.I)))))
nautica += rta(lambda r: r["objects_type_id"] == "Empresa de turismo activo" and re.search("diving|nautic|mar", r["name"], re.I),
               {"categoria": "Empresa de turismo activo"})
socorro = [feat(e, props_osm(e, nombre=nombre(e) or "Puesto de socorrismo"), True) for e in marcar(osm_sel(
    lambda e: T(e, "emergency") in ("lifeguard", "lifeguard_base") or T(e, "amenity") == "lifeguard", con_nombre=False))]

RE_ACADEMIA = re.compile(r"range|academ|school|escuela|lesson|driving|pitch ?& ?putt|practice", re.I)
academias = P(marcar(dedup(osm_sel(lambda e: (T(e, "golf") == "driving_range" or
                                               ((T(e, "leisure") == "golf_course" or T(e, "sport") == "golf")
                                                and RE_ACADEMIA.search(nombre(e)))) and T(e, "leisure") != "park"))))
campos = [feat(e, props_osm(e)) for e in marcar(dedup(osm_sel(
    lambda e: T(e, "leisure") == "golf_course" and nombre(e) not in ("Course A",))))]
tiendas_golf = P(marcar(osm_sel(lambda e: T(e, "shop") == "golf" or (T(e, "shop") and re.search("golf", nombre(e), re.I)))))


def distincion(guia):
    fs = []
    for d in DIST:
        if guia not in d:
            continue
        fs.append({"type": "Feature", "id": "dist-" + norm(d["nombre"]).replace(" ", "-"),
                   "properties": {k: v for k, v in {
                       "nombre": d["nombre"], "categoria": d[guia], "direccion": d.get("direccion"),
                       "otras_distinciones": " · ".join(f"{g}: {d[g]}" for g in ("Guía MICHELIN", "Guía Repsol")
                                                         if g in d and g != guia),
                       "fuente": d["fuente_" + ("michelin" if "MICHELIN" in guia else "repsol")],
                       "aviso": d.get("aviso")}.items() if v},
                   "geometry": {"type": "Point", "coordinates": d["lonlat"]}})
    return fs


for d in DIST:
    for e in E:
        if T(e, "amenity") in ("restaurant", "bar", "cafe") and Point(d["lonlat"]).distance(punto(e)["g"]) < 0.0008 \
                and norm(d["nombre"]).split()[0] in norm(nombre(e)):
            USADOS.add(e["id"])
chir = P(marcar(dedup(osm_sel(lambda e: T(e, "amenity") in ("restaurant", "bar", "cafe", "fast_food")
                                        and (cerca_playa(e) or re.search("chiringuito", nombre(e), re.I))))))
rest = [feat(e, props_osm(e, cocina=cocina(e["t"])), True) for e in marcar(dedup(osm_sel(
    lambda e: T(e, "amenity") == "restaurant")))]
bares = P(osm_sel(lambda e: T(e, "amenity") in ("bar", "pub", "cafe", "fast_food", "ice_cream", "biergarten")))
catering = P(marcar(osm_sel(lambda e: T(e, "craft") == "caterer" or T(e, "shop") == "caterer" or
                             re.search(r"catering", nombre(e), re.I))))
vino = P(marcar(dedup(osm_sel(lambda e: T(e, "shop") == "wine" or T(e, "amenity") == "wine_bar" or
                              (T(e, "amenity") in ("bar", "pub") and re.search(r"vino|wine|vinoteca|bodega", nombre(e), re.I))))))
deli = P(marcar(dedup(osm_sel(lambda e: T(e, "shop") in ("deli", "cheese", "gourmet", "delicatessen") or
                              (T(e, "shop") and re.search(r"gourmet|delicatessen|ib[eé]ric", nombre(e), re.I))))))
mercados = P(marcar(dedup(osm_sel(lambda e: T(e, "amenity") == "marketplace"))))

alb = P(marcar(osm_sel(lambda e: T(e, "tourism") == "hostel" and re.search(r"albergue|hostel|youth", nombre(e), re.I))))
camp = [feat(e, props_osm(e)) for e in marcar(osm_sel(lambda e: T(e, "tourism") == "camp_site"))]
hoteles_osm = P(osm_sel(lambda e: T(e, "tourism") in ("hotel", "apartment", "guest_house", "hostel", "motel")))

prot = [feat(e, props_osm(e)) for e in marcar(osm_sel(lambda e: (T(e, "boundary") == "protected_area" or
                                                                  T(e, "leisure") == "nature_reserve")
                                                      and e["g"].geom_type != "Point"))]
cumbres = [feat(e, props_osm(e, altitud=(T(e, "ele") + " m") if T(e, "ele") else None))
           for e in marcar(osm_sel(lambda e: T(e, "natural") in ("peak", "saddle")))]
mir = P(marcar(osm_sel(lambda e: T(e, "tourism") == "viewpoint")))
lago = marcar(osm_sel(lambda e: re.search(r"tortugas", nombre(e), re.I) and e["g"].geom_type != "Point")) \
       or marcar(osm_sel(lambda e: re.search(r"tortugas", nombre(e), re.I)))
lago = [feat(e, props_osm(e, otros_nombres="Embalse Viejo")) for e in lago]
parques = [feat(e, props_osm(e)) for e in marcar(dedup(osm_sel(
    lambda e: T(e, "leisure") in ("park", "garden") and e["g"].geom_type != "Point"
    and not re.search(r"golf|beach", nombre(e), re.I))))]
caninos = [feat(e, props_osm(e, nombre=nombre(e) or "Parque canino")) for e in marcar(osm_sel(
    lambda e: T(e, "leisure") == "dog_park", con_nombre=False))]


def ruta(cond):
    return [e for e in E if e["t"].get("type") == "route" and cond(e["t"])]


senda = [feat(e, props_osm(e, ref=T(e, "ref"))) for e in ruta(lambda t: "senda litoral" in norm(t.get("name")))]
gr = [feat(e, props_osm(e, ref=T(e, "ref"), etapa=nombre(e))) for e in ruta(
    lambda t: t.get("ref", "").replace("-", " ").startswith("GR 249"))]
senderos = [feat(e, props_osm(e, ref=T(e, "ref"))) for e in ruta(
    lambda t: t.get("route") == "hiking" and not t.get("ref", "").replace("-", " ").startswith(("GR 249", "GR 92"))
    and "senda litoral" not in norm(t.get("name")))]
carriles = [feat(e, props_osm(e, nombre=nombre(e) or "Carril bici")) for e in E
            if T(e, "highway") == "cycleway" and e["g"].geom_type in ("LineString", "MultiLineString")]
btt = [feat(e, props_osm(e, ref=T(e, "ref"))) for e in ruta(lambda t: t.get("route") in ("bicycle", "mtb"))]
bicis = P(marcar(osm_sel(lambda e: T(e, "amenity") == "bicycle_rental" or T(e, "shop") == "bicycle")))
activo_rta = rta(lambda r: r["objects_type_id"] == "Empresa de turismo activo" and not re.search("diving|nautic", r["name"], re.I),
                 {"categoria": "Empresa de turismo activo"})

arq = P(marcar(dedup(osm_sel(lambda e: T(e, "historic") == "archaeological_site" or
                             re.search(r"romana|romanas|paleocristiana|bóvedas", nombre(e), re.I)))))
torres_re = re.compile(r"torre (almenara|vig)|torre (de )?(rio real|las bovedas|el duque|ancon|lance|ladrones)", re.I)
mon = [feat(e, props_osm(e, tipo=T(e, "historic")), True) for e in marcar(dedup(osm_sel(
    lambda e: T(e, "historic") in ("castle", "fort", "tower", "city_gate", "ruins", "building", "monument", "manor",
                                   "watermill", "mine", "house", "church", "monastery", "wayside_cross",
                                   "boundary_stone", "industrial")
    or T(e, "man_made") == "watchtower" or torres_re.search(norm(nombre(e))))))]
rel = P(marcar(dedup(osm_sel(lambda e: T(e, "amenity") == "place_of_worship" and
                             re.search(r"iglesia|ermita|capilla|parroquia|convento|santuario|mezquita|templo|sinagoga",
                                       nombre(e), re.I)))))
mus = P(marcar(dedup(osm_sel(lambda e: T(e, "tourism") in ("museum", "gallery")))))
esc = P(marcar(dedup(osm_sel(lambda e: T(e, "amenity") in ("theatre", "arts_centre", "conference_centre",
                                                           "exhibition_centre", "community_centre", "library")
                             and not re.search("asociaci|vecinal", nombre(e), re.I)))))
art = [feat(e, props_osm(e, autor=T(e, "artist_name")), True) for e in marcar(dedup(osm_sel(
    lambda e: T(e, "tourism") == "artwork" or T(e, "historic") in ("memorial", "statue"))))]
plazas = P(osm_sel(lambda e: T(e, "place") == "square" or (T(e, "highway") == "pedestrian" and re.search("plaza", nombre(e), re.I))))

mall = P(marcar(dedup(osm_sel(lambda e: T(e, "shop") in ("mall", "department_store")))))
noc = P(marcar(dedup(osm_sel(lambda e: T(e, "amenity") in ("nightclub", "casino") or T(e, "leisure") == "dance"))))
fam = P(marcar(dedup(osm_sel(lambda e: T(e, "leisure") in ("water_park", "amusement_arcade", "miniature_golf", "bowling_alley") or
                             T(e, "tourism") in ("theme_park", "zoo", "aquarium") or
                             re.search(r"funny beach|aventura|pirate|karting", nombre(e), re.I)))))
cines = P(marcar(dedup(osm_sel(lambda e: T(e, "amenity") == "cinema"))))
deporte_osm = P(osm_sel(lambda e: T(e, "leisure") in ("fitness_centre", "sports_centre", "horse_riding")
                        or T(e, "sport") in ("tennis", "padel", "equestrian", "yoga", "fitness")))

ofi = P(marcar(dedup(osm_sel(lambda e: T(e, "tourism") == "information" and T(e, "information") == "office"))))
ofi += [f for f in rta(lambda r: r["objects_type_id"] == "Oficina de turismo")
        if all(Point(f["geometry"]["coordinates"]).distance(shape(o["geometry"])) > 0.001 for o in ofi)]
park = [feat(e, props_osm(e, tipo=T(e, "parking"), plazas=T(e, "capacity")), True) for e in marcar(dedup(osm_sel(
    lambda e: T(e, "amenity") == "parking" and (T(e, "parking") in ("underground", "multi-storey") or nombre(e))
    and T(e, "access") not in ("private", "customers"))))]
bus = P(marcar(dedup(osm_sel(lambda e: T(e, "amenity") == "bus_station"))))
taxi = [feat(e, props_osm(e, nombre=nombre(e) or "Parada de taxi"), True)
        for e in marcar(osm_sel(lambda e: T(e, "amenity") == "taxi", con_nombre=False))]
recarga = [feat(e, props_osm(e, nombre=nombre(e) or T(e, "operator") or "Punto de recarga"), True)
           for e in marcar(osm_sel(lambda e: T(e, "amenity") == "charging_station", con_nombre=False))]
farmacias = [feat(e, props_osm(e, nombre=nombre(e) or "Farmacia"), True)
             for e in marcar(osm_sel(lambda e: T(e, "amenity") == "pharmacy", con_nombre=False))]
salud = P(marcar(dedup(osm_sel(lambda e: T(e, "amenity") == "hospital" or
                               (T(e, "amenity") in ("clinic", "doctors") and re.search(r"centro de salud|urgencia|hospital|consultorio", nombre(e), re.I))))))
clinicas = P(osm_sel(lambda e: T(e, "amenity") in ("clinic", "doctors", "veterinary", "dentist") or T(e, "shop") in ("beauty", "pet", "pet_grooming")
                     or T(e, "leisure") == "sauna" or T(e, "amenity") == "spa"))
policia = [feat(e, props_osm(e, nombre=nombre(e) or "Policía"), True)
           for e in marcar(dedup(osm_sel(lambda e: T(e, "amenity") == "police", con_nombre=False)))]
aseos = [feat(e, props_osm(e, nombre=nombre(e) or "Aseo público", accesible="Sí" if T(e, "wheelchair") == "yes" else None), True)
         for e in marcar(osm_sel(lambda e: T(e, "amenity") == "toilets", con_nombre=False))]
comercio = P(osm_sel(lambda e: T(e, "shop") in ("clothes", "boutique", "fashion", "jewelry", "shoes", "bag", "watches", "florist",
                                               "bakery", "pastry", "confectionery", "copyshop", "stationery", "travel_agency",
                                               "car_rental", "bureau_de_change") or T(e, "amenity") in ("car_rental", "bureau_de_change")
                     or T(e, "office") in ("travel_agent", "coworking", "company")))

TODO = (rest + bares + hoteles_osm + comercio + clinicas + deporte_osm + plazas + mon + mus + esc + art + rel + arq)

# ================================================================================================
print("Construyendo capas...")

# 1. MAR -----------------------------------------------------------------------------------------
grupo("mar", "Mar", "#0E7FB8", "Litoral, playas, puertos y actividades náuticas.", "/vive/mar")
sub("actividades_nauticas", "Actividades náuticas", con_web(web("/vive/mar/actividades-nauticas"), nautica, TODO + clubes),
    "punto", F_WEB + "; " + F_OSM + "; " + F_RTA,
    "Empresas y clubes de actividades náuticas: motos de agua, vela, buceo, paddle surf, esquí acuático.",
    web=["/vive/mar/actividades-nauticas"])
sub("playas", "Playas", con_web(web("/vive/mar/playas"), playas, radio=0.006), "polígono", F_WEB + "; " + F_OSM + "; Bandera Azul: ADEAC 2026",
    "Las playas del término. Atributo de Bandera Azul (ADEAC, temporada 2026).", visible=True, web=["/vive/mar/playas"])
sub("puertos", "Puertos", con_web(web("/vive/mar/puertos"), puertos, radio=0.006), "polígono", F_WEB + "; " + F_OSM,
    "Puertos José Banús, Virgen del Carmen (puerto deportivo de Marbella), Marina La Bajadilla y Cabopino.",
    web=["/vive/mar/puertos"])
sub("clubes_playa", "Clubs de playa", con_web(web("/vive/mar/clubs-de-playa"), clubes, TODO + chir), "punto",
    F_WEB + "; " + F_OSM, "Clubs de playa (beach clubs) con restauración, hamacas y servicios.",
    web=["/vive/mar/clubs-de-playa"])
sub("buceo", "Zonas de submarinismo", con_web(web("/vive/mar/buceo")), "punto", F_WEB,
    "Zonas de inmersión: El Galeón, La Torre, Las Bóvedas, Pimpollo y Roqueillos.", web=["/vive/mar/buceo"])
sub("salvamento", "Salvamento y socorrismo", socorro, "punto", F_OSM,
    "Puestos de salvamento y socorrismo en playa (complementaria).",
    pendiente="Completar con el plan de salvamento y socorrismo de cada temporada")

# 2. GOLF ----------------------------------------------------------------------------------------
grupo("golf", "Golf", "#3A8D3F", "Campos de golf y servicios al golfista.", "/vive/golf")
CAMPOS = [r["pagina"][:-5] for r in web("/vive/golf") if r["pagina"].count("/") == 3
          and not re.search(r"academias|tiendas|alquiler", r["pagina"])]
sub("campos_golf", "Campos de golf", con_web(web(*CAMPOS), campos, radio=0.008), "polígono", F_WEB + "; " + F_OSM,
    "Los campos de golf del término, cada uno con su ficha.", web=sorted(set(CAMPOS)))
sub("academias_golf", "Academias y escuelas de golf", con_web(web("/vive/golf/academias-y-escuelas-de-golf"), academias, campos + TODO),
    "punto", F_WEB + "; " + F_OSM, "Academias, escuelas y campos de prácticas.",
    web=["/vive/golf/academias-y-escuelas-de-golf"])
sub("tiendas_golf", "Tiendas de golf", con_web(web("/vive/golf/tiendas-de-golf"), tiendas_golf, TODO), "punto",
    F_WEB + "; " + F_OSM, "Tiendas especializadas en golf.", web=["/vive/golf/tiendas-de-golf"])
sub("alquiler_golf", "Alquiler de equipos de golf", con_web(web("/vive/golf/alquiler-de-equipos-de-golf"), ajenos=TODO),
    "punto", F_WEB, "Alquiler de palos y material.", web=["/vive/golf/alquiler-de-equipos-de-golf"])

# 3. GASTRONOMÍA ---------------------------------------------------------------------------------
grupo("gastronomia", "Gastronomía", "#C0392B", "Restauración, distinciones y producto local.", "/vive/gastronomia")
sub("michelin", "Estrellas Michelin", con_web(web("/vive/gastronomia/estrellas-michelin"), distincion("Guía MICHELIN")),
    "punto", "Guía MICHELIN España 2026; " + F_WEB, "Restaurantes con Estrella MICHELIN (edición 2026).",
    color="#B3001B", web=["/vive/gastronomia/estrellas-michelin"])
sub("repsol", "Soles Repsol", con_web(web("/vive/gastronomia/soles-repsol"), distincion("Guía Repsol")),
    "punto", "Guía Repsol 2026; " + F_WEB, "Restaurantes con Sol Repsol (edición 2026).", color="#E67E22",
    web=["/vive/gastronomia/soles-repsol"])
sub("saboreando", "Saboreando Marbella", con_web(web("/vive/gastronomia/saboreando"), ajenos=TODO + vino + deli),
    "punto", F_WEB, "Propuesta gastronómica «Saboreando Marbella»: producto, bodegas y lugares donde probarlo.",
    web=["/vive/gastronomia/saboreando"])
sub("restaurantes", "Restaurantes destacados", con_web(web("/vive/gastronomia/restaurantes-destacados"), ajenos=TODO + chir + clubes),
    "punto", F_WEB + "; " + F_OSM, "Restaurantes destacados.", web=["/vive/gastronomia/restaurantes-destacados"])
sub("chiringuitos", "Chiringuitos", con_web(web("/vive/gastronomia/chiringuitos"), chir, TODO + clubes), "punto",
    F_WEB + "; " + F_OSM, "Chiringuitos y restaurantes de playa.", web=["/vive/gastronomia/chiringuitos"])
sub("catering", "Catering", con_web(web("/vive/gastronomia/catering"), catering, TODO), "punto", F_WEB + "; " + F_OSM,
    "Empresas de catering.", web=["/vive/gastronomia/catering"])
sub("vinotecas", "Vinotecas", con_web(web("/vive/gastronomia/vinotecas"), vino, TODO + deli), "punto", F_WEB + "; " + F_OSM,
    "Vinotecas y tiendas de vino.", web=["/vive/gastronomia/vinotecas"])
sub("delicatessen", "Delicatessen", con_web(web("/vive/gastronomia/delicatessen"), deli, TODO + vino), "punto",
    F_WEB + "; " + F_OSM, "Tiendas gourmet y de producto selecto.", web=["/vive/gastronomia/delicatessen"])
otros_rest = sobrantes(rest)
sub("otros_restaurantes", "Otros restaurantes", otros_rest, "punto", F_OSM,
    "Restaurantes del municipio que la web no destaca (complementaria).")

# 4. ALOJAMIENTOS --------------------------------------------------------------------------------
grupo("alojamientos", "Alojamientos", "#7D3C98", "Alojamiento turístico reglado, por categorías.", "/vive/alojamientos")
ESTR = lambda c: int(m.group(1)) if (m := re.search(r"(\d)", c or "")) else None


def rta_cat(tipo, grupo_rta, estrellas=None, gl=False):
    def cond(r):
        if r["objects_type_id"] != tipo or (grupo_rta and r.get("group") != grupo_rta):
            return False
        if estrellas is None:
            return True
        es_gl = "lujo" in norm(r.get("categories")) or "gl" in norm(r.get("categories")).split()
        return ESTR(r.get("categories")) == estrellas and es_gl == gl
    return rta(cond)


EH = "Establecimiento Hotelero"
ALOJ = [  # (id, título como en la web, página, entidades del RTA de esa categoría)
    ("hoteles_5gl", "Hoteles ***** GL", "hoteles-5gl", rta_cat(EH, "Hotel", 5, True)),
    ("hoteles_5", "Hoteles *****", "hoteles-5e", rta_cat(EH, "Hotel", 5)),
    ("hoteles_4", "Hoteles ****", "hoteles-4e", rta_cat(EH, "Hotel", 4)),
    ("hoteles_3", "Hoteles ***", "hoteles-3e", rta_cat(EH, "Hotel", 3)),
    ("hoteles_2", "Hoteles **", "hoteles-2e", rta_cat(EH, "Hotel", 2)),
    ("hoteles_1", "Hoteles *", "hoteles-1e", rta_cat(EH, "Hotel", 1)),
    ("hoteles_apto_4", "Hoteles Apto. ****", "hoteles-apartamento-4e", rta_cat(EH, "Hotel-Apartamento", 4)),
    ("hoteles_apto_3", "Hoteles Apto. ***", "hoteles-apto", rta_cat(EH, "Hotel-Apartamento", 3) + rta_cat(EH, "Hotel-Apartamento", 2)),
    ("hostales_2", "Hostales **", "hostales-2e", rta_cat(EH, "Hostal", 2)),
    ("hostales_1", "Hostales *", "hostales-1e", rta_cat(EH, "Hostal", 1)),
    ("at_4", "AT 4 llaves", "at-4-llaves", rta_cat("Apartamento turístico", None, 4)),
    ("at_3", "AT 3 llaves", "at-3-llaves", rta_cat("Apartamento turístico", None, 3)),
    ("at_2", "AT 2 llaves", "at-2-llaves", rta_cat("Apartamento turístico", None, 2)),
    ("at_1", "AT 1 llave", "at-1-llave", rta_cat("Apartamento turístico", None, 1)),
    ("pensiones", "Pensiones", "pensiones", rta_cat(EH, "Pensión")),
    ("albergues", "Albergues y residencias", "albergues-y-residencias", alb),
    ("campings", "Campings", "campings", camp),
]
asignados_rta = {f["id"] for *_, fs in ALOJ for f in fs}
resto_rta = rta(lambda r: r["objects_type_id"] in (EH, "Apartamento turístico"))
resto_rta = [f for f in resto_rta if f["id"] not in asignados_rta]
todos_aloj = [f for *_, fs in ALOJ for f in fs] + resto_rta + hoteles_osm
for sid, tit, pag, fs in ALOJ:
    ruta_w = "/vive/alojamientos/" + pag
    sub(sid, tit, con_web(web(ruta_w), fs, [f for f in todos_aloj if f not in fs], etiqueta=True),
        "polígono" if sid == "campings" else "punto", F_WEB + "; " + (F_OSM if sid in ("albergues", "campings") else F_RTA),
        f"{tit.replace('AT ', 'Apartamentos turísticos de ').replace('Apto.', 'apartamento')}.", web=[ruta_w])
sub("aloj_otros", "Otros alojamientos registrados", sobrantes(resto_rta), "punto", F_RTA,
    "Establecimientos inscritos en el RTA de categorías que la web no recoge (complementaria).")
sub("rural", "Alojamiento rural", rta(lambda r: r["objects_type_id"] in ("Casa rural", "Vivienda turística de alojamiento rural")),
    "punto", F_RTA, "Casas rurales y viviendas turísticas de alojamiento rural (complementaria).")

# 5. NATURALEZA ----------------------------------------------------------------------------------
grupo("naturaleza", "Naturaleza", "#2E7D32", "Espacios naturales, sierra, parques, senderos y turismo activo.",
      "/vive/naturaleza")
sub("dunas_artola", "Dunas de Artola", con_web(web("/vive/naturaleza/dunas-de-artola"), prot, radio=0.01), "polígono",
    F_WEB + "; " + F_OSM + "; REDIAM (servicio WMS)", "Monumento Natural Dunas de Artola (Cabopino).",
    web=["/vive/naturaleza/dunas-de-artola"])
sub("lago_tortugas", "Lago de las Tortugas", con_web(web("/vive/naturaleza/lago-de-las-tortugas"), lago, radio=0.01),
    "polígono", F_WEB + "; " + F_OSM, "Lago de las Tortugas, antiguamente denominado Embalse Viejo.",
    web=["/vive/naturaleza/lago-de-las-tortugas"])
sub("senda_litoral", "Senda del Litoral", con_web(web("/vive/naturaleza/senda-del-litoral"), senda, radio=0.06), "línea",
    F_WEB + "; " + F_OSM, "Senda Litoral de la provincia de Málaga a su paso por Marbella (también señalizada como GR 92).",
    color="#0097A7", web=["/vive/naturaleza/senda-del-litoral"])
sub("cicloturismo", "Cicloturismo", con_web(web("/vive/naturaleza/cicloturismo-2"), bicis, TODO), "punto",
    F_WEB + "; " + F_OSM, "Alquiler, tiendas y rutas guiadas en bicicleta.", color="#F39C12",
    web=["/vive/naturaleza/cicloturismo-2"])
sub("turismo_activo", "Turismo activo", con_web(web("/vive/naturaleza/turismo-activo"), activo_rta, TODO), "punto",
    F_WEB + "; " + F_RTA, "Empresas de turismo activo y guías de montaña.", color="#E67E22",
    web=["/vive/naturaleza/turismo-activo"])
sub("cumbres", "Sierra Blanca: cumbres", con_web(web("/vive/naturaleza/sierra-blanca", excepto=["/vive/naturaleza/sierra-blanca/rutas-de-senderismo"]),
                                                 cumbres, mir, radio=0.01), "punto", F_WEB + "; " + F_OSM,
    "Cumbres de Sierra Blanca: La Concha, Cruz de Juanar, Tajo Negro, Salto del Lobo, Lastonar…",
    web=["/vive/naturaleza/sierra-blanca", "/vive/naturaleza/sierra-blanca/cumbres-de-la-sierra"])
sub("senderos", "Sierra Blanca: rutas de senderismo", con_web(web("/vive/naturaleza/sierra-blanca/rutas-de-senderismo"),
                                                              senderos, gr, radio=0.02, por_ref=True), "línea",
    F_WEB + "; " + F_OSM, "Senderos de Sierra Blanca (PR-A y SL-A). Las que tienen trazado en OpenStreetMap se "
                          "dibujan como línea; el resto, en su punto de inicio.", color="#6D4C41",
    web=["/vive/naturaleza/sierra-blanca/rutas-de-senderismo"])
sub("parques", "Parques y jardines", con_web(web("/vive/naturaleza/parques-y-jardines"), parques, radio=0.004), "polígono",
    F_WEB + "; " + F_OSM, "Parques urbanos y jardines (Alameda, La Represa, Arroyo de la Represa, El Mirador…).",
    web=["/vive/naturaleza/parques-y-jardines"])
sub("gr249", "Gran Senda de Málaga (GR-249)", sobrantes(gr), "línea", F_OSM,
    "Etapas Estepona–Marbella y Marbella–Ojén de la Gran Senda de Málaga (complementaria).", color="#D84315")
sub("miradores", "Miradores", sobrantes(mir), "punto", F_OSM, "Miradores con nombre (complementaria).")
sub("carriles_bici", "Carriles bici", carriles, "línea", F_OSM, "Red de carriles bici (complementaria).", color="#F39C12")
sub("rutas_ciclistas", "Rutas cicloturistas y BTT", btt, "línea", F_OSM,
    "Rutas ciclistas señalizadas (complementaria).", color="#AF601A")

# 6. COMPRAS -------------------------------------------------------------------------------------
grupo("compras", "Compras", "#D81B60", "Mercados, centros comerciales y firmas de moda.", "/vive/compras")
sub("mercadillos", "Mercadillos y mercados", con_web(web("/vive/compras/mercados-de-abastos-y-mercadillos"), mercados, TODO),
    "punto", F_WEB + "; " + F_OSM, "Mercados municipales de abastos y mercadillos.",
    web=["/vive/compras/mercados-de-abastos-y-mercadillos"])
sub("centros_comerciales", "Centros comerciales", con_web(web("/vive/compras/centros-comerciales"), mall, TODO), "punto",
    F_WEB + "; " + F_OSM, "Centros comerciales y grandes almacenes.", web=["/vive/compras/centros-comerciales"])
sub("firmas_moda", "Firmas de moda", con_web(web("/vive/compras/firmas-de-moda"), ajenos=TODO), "punto", F_WEB,
    "Tiendas de las grandes firmas de moda (Puerto Banús, Marbella Club, Puente Romano, La Cañada…).",
    web=["/vive/compras/firmas-de-moda"])

# 7. CULTURA -------------------------------------------------------------------------------------
grupo("cultura", "Cultura", "#8E5B3E", "Centros culturales, galerías y patrimonio histórico.", "/vive/cultura")
CULT = mon + mus + esc + art + rel + arq + plazas + parques
sub("centros_culturales", "Centros culturales municipales", con_web(web("/vive/cultura/centros-culturales-municpales"), ajenos=CULT + TODO),
    "punto", F_WEB + "; " + F_OSM, "Teatro, museos, bibliotecas, escuelas de música y centros culturales municipales.",
    web=["/vive/cultura/centros-culturales-municpales"])
sub("galerias", "Galerías y talleres de arte", con_web(web("/vive/cultura/galerias-y-talleres-de-arte"), ajenos=CULT + TODO),
    "punto", F_WEB, "Galerías de arte y talleres de artistas.", web=["/vive/cultura/galerias-y-talleres-de-arte"])
sub("casco_historico", "Casco histórico", con_web(web("/vive/cultura/patrimonio-historico/casco-historico"), ajenos=CULT + TODO),
    "punto", F_WEB + "; " + F_OSM, "Plazas, iglesias y edificios del casco antiguo.",
    web=["/vive/cultura/patrimonio-historico/casco-historico"])
sub("torres_vigia", "Torres vigía", con_web(web("/vive/cultura/patrimonio-historico/torres-vigia"), ajenos=CULT, radio=0.006),
    "punto", F_WEB + "; " + F_OSM, "Torres almenaras de la costa.", web=["/vive/cultura/patrimonio-historico/torres-vigia"])
sub("arqueologia", "Arqueología", con_web(web("/vive/cultura/patrimonio-historico/arqueologia"), ajenos=CULT, radio=0.006),
    "punto", F_WEB + "; " + F_OSM, "Villa romana de Río Verde, termas de Las Bóvedas, basílica de Vega del Mar, "
                                   "yacimiento fenicio de Río Real…", web=["/vive/cultura/patrimonio-historico/arqueologia"])
sub("patrimonio_industrial", "Patrimonio industrial", con_web(web("/vive/cultura/patrimonio-historico/patrimonio-industrial"),
                                                             ajenos=CULT, radio=0.006),
    "punto", F_WEB + "; " + F_OSM, "Trapiches, ferrería, mina y el cargadero de El Cable.",
    web=["/vive/cultura/patrimonio-historico/patrimonio-industrial"])
sub("patrimonio_religioso", "Patrimonio religioso", sobrantes(rel), "punto", F_OSM,
    "Iglesias, ermitas y templos (complementaria).")
sub("monumentos", "Otros monumentos y museos", sobrantes(mon + mus + arq), "punto", F_OSM,
    "Monumentos, edificios históricos y museos no citados en la web (complementaria).")
sub("arte_urbano", "Arte en la calle", sobrantes(art), "punto", F_OSM,
    "Esculturas y arte público: las esculturas de Dalí de la Avenida del Mar, monumentos y estatuas (complementaria).")

# 8. DEPORTE -------------------------------------------------------------------------------------
grupo("deporte", "Deporte", "#1565C0", "Instalaciones y centros deportivos.", "/vive/deporte")
for sid, tit, pag, desc in [("equitacion", "Centros de equitación", "centros-de-equitacion", "Centros hípicos y de equitación."),
                            ("gimnasios", "Gimnasios multidisciplinas", "gimnasios", "Gimnasios, centros deportivos y boxes."),
                            ("tenis_padel", "Tenis y pádel", "tenis-y-padel", "Clubes y academias de tenis y pádel."),
                            ("yoga", "Yoga y pilates", "yoga", "Centros de yoga y pilates.")]:
    sub(sid, tit, con_web(web("/vive/deporte/" + pag), ajenos=TODO), "punto", F_WEB, desc, web=["/vive/deporte/" + pag])

# 9. SALUD Y BIENESTAR ---------------------------------------------------------------------------
grupo("salud", "Salud y bienestar", "#00897B", "Spas, estética y servicios sanitarios.", "/vive/salud-y-bienestar")
sub("spa", "Centros de spa", con_web(web("/vive/salud-y-bienestar/centros-spa"), ajenos=TODO), "punto", F_WEB,
    "Spas y centros de bienestar.", web=["/vive/salud-y-bienestar/centros-spa"])
sub("estetica", "Clínicas de estética", con_web(web("/vive/salud-y-bienestar/clinicas-de-estetica"), ajenos=TODO),
    "punto", F_WEB, "Clínicas de medicina y cirugía estética.", web=["/vive/salud-y-bienestar/clinicas-de-estetica"])
sub("salud", "Turismo salud", con_web(web("/vive/salud-y-bienestar/hospitales-y-clinicas-centros-de-salud"), salud, TODO),
    "punto", F_WEB + "; " + F_OSM, "Hospitales, clínicas y centros de salud públicos y privados.",
    web=["/vive/salud-y-bienestar/hospitales-y-clinicas-centros-de-salud"])

# 10. OCIO ---------------------------------------------------------------------------------------
grupo("ocio", "Ocio", "#AD1457", "Flamenco, ocio familiar y nocturno, terrazas.", "/vive/ocio")
sub("flamenco", "Espectáculos flamencos", con_web(web("/vive/ocio/espectaculos-flamencos"), ajenos=TODO), "punto", F_WEB,
    "Tablaos y locales con espectáculo flamenco.", web=["/vive/ocio/espectaculos-flamencos"])
sub("ocio_familiar", "Ocio familiar", con_web(web("/vive/ocio/ocio"), fam, TODO + cines), "punto", F_WEB + "; " + F_OSM,
    "Parques de aventura, karting, bolera, cines, escape rooms y parques temáticos de la Costa del Sol.",
    web=["/vive/ocio/ocio"])
sub("ocio_nocturno", "Ocio nocturno", con_web(web("/vive/ocio/nocturno"), noc, TODO), "punto", F_WEB + "; " + F_OSM,
    "Discotecas, salas, bares de copas y casino.", web=["/vive/ocio/nocturno"])
sub("rooftops", "Terrazas rooftops", con_web(web("/vive/ocio/terrazas-rooftop"), ajenos=TODO), "punto", F_WEB,
    "Terrazas en azotea.", web=["/vive/ocio/terrazas-rooftop"])
sub("cines", "Cines", sobrantes(cines), "punto", F_OSM, "Salas de cine (complementaria).")

# 11. VIAJAR CON MASCOTAS ------------------------------------------------------------------------
grupo("mascotas", "Viajar con mascotas", "#6D4C41", "Servicios y lugares para viajar con mascotas.",
      "/vive/viajar-con-mascotas")
sub("veterinarios", "Veterinarios", con_web(web("/vive/viajar-con-mascotas/veterinarios"), ajenos=TODO), "punto", F_WEB,
    "Clínicas veterinarias.", web=["/vive/viajar-con-mascotas/veterinarios"])
sub("servicios_mascotas", "Servicios para mascotas", con_web(web("/vive/viajar-con-mascotas/servicios-para-mascotas"), ajenos=TODO),
    "punto", F_WEB, "Peluquerías caninas, tiendas y otros servicios.", web=["/vive/viajar-con-mascotas/servicios-para-mascotas"])
sub("hoteles_mascotas", "Hoteles para mascotas", con_web(web("/vive/viajar-con-mascotas/hoteles-para-mascotas"), ajenos=TODO),
    "punto", F_WEB, "Residencias y hoteles para mascotas.", web=["/vive/viajar-con-mascotas/hoteles-para-mascotas"])
sub("parques_caninos", "Parques caninos", con_web(web("/vive/viajar-con-mascotas/parques-caninos"), caninos, parques), "punto",
    F_WEB + "; " + F_OSM, "Parques y zonas de esparcimiento canino.", web=["/vive/viajar-con-mascotas/parques-caninos"])
pet = [r for r in WEBR if r["pagina"] == "/vive/viajar-con-mascotas.html"]
sub("admiten_mascotas", "Admiten mascotas", con_web(pet, ajenos=todos_aloj + playas + park, etiqueta=True), "punto", F_WEB,
    "Alojamientos, playas y aparcamientos que admiten mascotas.", web=["/vive/viajar-con-mascotas"])

# 12. SERVICIOS TURÍSTICOS -----------------------------------------------------------------------
grupo("servicios", "Servicios turísticos", "#455A64", "Oficinas de turismo y empresas de servicios turísticos.",
      "/servicios/servicios-turisticos")
sub("oficinas_turismo", "Oficinas de información turística", con_web(web("/servicios/oficinas-de-informacion-turistica"), ofi),
    "punto", F_WEB + "; " + F_OSM + "; " + F_RTA, "Oficinas municipales de turismo.",
    web=["/servicios/oficinas-de-informacion-turistica"])
for sid, tit, pag, desc in [
        ("agencias", "Agencias de viajes", "agencias-de-viajes", "Agencias de viajes."),
        ("alquiler_coches", "Alquiler de coches", "alquiler-de-coches", "Alquiler de vehículos."),
        ("guias", "Guías turísticos", "guias-turisticos", "Guías oficiales y empresas de visitas guiadas."),
        ("alquiler_autobuses", "Alquiler de autobuses", "alquiler-de-autobuses", "Autocares con conductor."),
        ("alquiler_barcos", "Alquiler de barcos", "alquiler-de-barcos", "Chárter y alquiler de embarcaciones."),
        ("transfer", "Transfer", "transfer", "Traslados y transporte con conductor."),
        ("alquiler_aereo", "Alquiler aéreo", "alquiler-de-aviones-y-helicopteros", "Aviones y helicópteros."),
        ("caravanas", "Caravanas", "facilidades-caravanas", "Servicios para autocaravanas y alquiler de campers."),
        ("experiencias", "Experiencias", "experiencias-en-marbella", "Experiencias y excursiones."),
        ("cambio", "Oficinas de cambio", "oficinas-de-cambio", "Cambio de divisas."),
        ("consigna", "Consigna de equipajes", "consigna-equipajes", "Consignas y taquillas de equipaje.")]:
    ruta_w = "/servicios/servicios-turisticos/" + pag
    sub(sid, tit, con_web(web(ruta_w), ajenos=TODO + nautica + bicis), "punto", F_WEB, desc, web=[ruta_w])
sub("ruta_fotografica", "Ruta fotográfica", con_web(web("/servicios/ruta-fotografica-de-marbella")), "punto", F_WEB,
    "Los puntos de la ruta fotográfica de Marbella.", color="#7E57C2", web=["/servicios/ruta-fotografica-de-marbella"])

# 13. MARBELLA DE BODA ---------------------------------------------------------------------------
grupo("bodas", "Marbella de boda", "#C2185B", "Lugares y servicios para celebrar una boda.", "/servicios/marbella-de-boda")
B = "/servicios/marbella-de-boda/"
for sid, tit, pag, desc, aj in [
        ("bodas_lugares", "Lugares de celebración", "lugares-de-celebracion", "Fincas y espacios para celebraciones.", TODO),
        ("bodas_ceremonias", "Lugares de ceremonias religiosas", "lugares-de-ceremonias-religiosas",
         "Iglesias y templos de distintas confesiones.", rel + CULT),
        ("bodas_organizadores", "Organizadores de eventos", "organizadores-de-eventos", "Wedding planners.", TODO),
        ("bodas_oficiantes", "Oficiantes de ceremonia", "oficiantes", "Oficiantes de ceremonias civiles.", TODO),
        ("bodas_complementarios", "Servicios complementarios", "servicios-complementarios",
         "Floristas, fotografía, música, papelerías, tartas y tiendas de novias.", TODO),
        ("bodas_alquiler", "Servicios de alquiler", "servicios-de-alquiler", "Alquiler de mobiliario y decoración.", TODO)]:
    recs = web(B + pag)
    if sid == "bodas_organizadores":
        recs += [r for r in WEBR if r["pagina"] == "/servicios/marbella-de-boda.html"]
    fs = con_web(recs, ajenos=aj)
    if sid == "bodas_complementarios":     # la categoría (floristas, música…) es la subpágina
        tipo = {norm(titulo_web(r)): r["pagina_titulo"] for r in recs}
        for f in fs:
            f["properties"].setdefault("categoria", tipo.get(norm(f["properties"]["nombre"])))
    sub(sid, tit, fs, "punto", F_WEB, desc, web=[B + pag])

# 14. ÁREA PROFESIONAL ---------------------------------------------------------------------------
grupo("profesional", "Congresos y empresas", "#5D4037", "Congresos y eventos (MICE) y empresas turísticas.",
      "/area-profesional/mice-congresos-y-eventos")
M = "/area-profesional/mice-congresos-y-eventos/"
sub("mice_recintos", "Recintos para congresos y eventos", con_web(web(M + "marbella-arena", M + "palacio-de-congresos-y-exposiciones"),
                                                                ajenos=esc + TODO),
    "punto", F_WEB, "Palacio de Congresos y Exposiciones y Marbella Arena.",
    web=[M + "marbella-arena", M + "palacio-de-congresos-y-exposiciones"])
for sid, tit, pag, desc in [("mice_negocios", "Centros de negocios", "centros-de-negocios", "Centros de negocios y coworking."),
                            ("mice_traductores", "Traductores", "traductores", "Traductores e intérpretes."),
                            ("mice_azafatas", "Azafatas", "azafatas", "Agencias de azafatas."),
                            ("mice_dmc", "DMC's", "dmc-s", "Agencias receptivas de eventos (DMC).")]:
    sub(sid, tit, con_web(web(M + pag), ajenos=TODO), "punto", F_WEB, desc, web=[M + pag])
sub("empresas_turisticas", "Empresas turísticas", con_web(web("/area-profesional/empresas-turisticas"), etiqueta=True),
    "punto", F_WEB, "Asociaciones turísticas y turoperadores.", web=["/area-profesional/empresas-turisticas"])

# 15. INFORMACIÓN PRÁCTICA -----------------------------------------------------------------------
grupo("practica", "Información práctica", "#37474F", "Aparcamiento, movilidad, contactos de interés y otros servicios.",
      "/descubre/aparcamiento")
sub("aparcamientos", "Aparcamientos", con_web(web("/descubre/aparcamiento"), park, radio=0.003, etiqueta=True), "punto",
    F_WEB + "; " + F_OSM, "Aparcamientos públicos, de centros comerciales y de playa, y zona azul.",
    web=["/descubre/aparcamiento"])
sub("movilidad", "Movilidad", con_web(web("/descubre/movilidad", "/servicios/contactos-de-interes/transportes"), bus + taxi),
    "punto", F_WEB + "; " + F_OSM, "Estaciones de autobuses, paradas de taxi, tren y aeropuerto.",
    web=["/descubre/movilidad", "/servicios/contactos-de-interes/transportes"])
sub("emergencias", "Emergencias", con_web(web("/servicios/contactos-de-interes/emergencias"), policia, TODO), "punto",
    F_WEB + "; " + F_OSM, "Policía, Protección Civil, Salvamento Marítimo y teléfonos de emergencia.",
    web=["/servicios/contactos-de-interes/emergencias"])
sub("contactos_otros", "Otros contactos de interés", con_web(web("/servicios/contactos-de-interes/otros"), ajenos=TODO),
    "punto", F_WEB, "Ayuntamiento, Correos, Extranjería y otros servicios.", web=["/servicios/contactos-de-interes/otros"])
sub("farmacias", "Farmacias", farmacias, "punto", F_OSM, "Farmacias (complementaria).")
sub("aseos", "Aseos públicos", aseos, "punto", F_OSM, "Aseos públicos, incluidos los de playa (complementaria).")
sub("recarga", "Puntos de recarga eléctrica", recarga, "punto", F_OSM, "Puntos de recarga de vehículo eléctrico (complementaria).",
    pendiente="Completar con el Punto de Acceso Nacional de recarga (MITMA/DGT)")

# -- control: ningún recurso de la web fuera del mapa ---------------------------------------------
faltan = [r for r in WEBR if r["i"] not in WEB_USADOS]
if faltan:
    grupo("control", "Otros recursos de la web", "#9E9E9E", "Recursos de la web aún sin subcapa propia.")
    sub("otros_web", "Sin subcapa asignada", con_web(faltan, etiqueta=True), "punto", F_WEB,
        "Recursos publicados en la web en páginas que este visor aún no tiene asignadas a una subcapa.",
        web=sorted({r["pagina"][:-5] for r in faltan}))
    print("AVISO:", len(faltan), "recursos de la web sin subcapa:", sorted({r["pagina"] for r in faltan}))

# -- término y catálogo ----------------------------------------------------------------------------
json.dump({"type": "Feature", "properties": {"nombre": "Término municipal de Marbella"},
           "geometry": geom({"g": TERMINO}, 0.0001)}, open(os.path.join(OUT, "termino.geojson"), "w"), separators=(",", ":"))
json.dump(cache_geo, open(CACHE_GEO, "w", encoding="utf8"), ensure_ascii=False, indent=1)
for g in CAT:
    for s in g["subcapas"]:
        s["complementaria"] = not s["web"]
json.dump({"generado": date.today().isoformat(), "grupos": CAT}, open(os.path.join(OUT, "catalogo.json"), "w",
                                                                      encoding="utf8"), ensure_ascii=False, indent=1)

# -- informe de cobertura ---------------------------------------------------------------------------
sid_de = {i: sid for sid, ids in ASIGNACION.items() for i in ids}
tit_de = {s["id"]: (g["titulo"], s["titulo"]) for g in CAT for s in g["subcapas"]}
paginas_sub = {w[len(URL_WEB):] for g in CAT for s in g["subcapas"] for w in (s["web"] or [])}


def pagina_de(p):
    """Página de categoría a la que pertenece una ficha (los aparcamientos, por ejemplo, tienen página propia)."""
    partes = p[:-5].split("/")
    for i in range(len(partes), 1, -1):
        if "/".join(partes[:i]) + ".html" in paginas_sub:
            return "/".join(partes[:i]) + ".html"
    return p


por_pag = {}
for r in WEBR:
    por_pag.setdefault(pagina_de(r["pagina"]), []).append(r)
lin = ["# Cobertura de la web de turismo en el visor", "",
       f"Generado el {date.today().isoformat()} a partir de {len(WEBR)} entradas de turismo.marbella.es "
       f"({len({norm(titulo_web(r)) for r in WEBR})} recursos distintos).", "",
       "| Página de la web | Recursos | Capa · subcapa del visor | Sin ubicación |", "|---|---:|---|---:|"]
sin_ub = {f["properties"]["ficha"] for g in CAT for s in g["subcapas"] if s["sin_ubicacion"]
          for f in json.load(open(os.path.join(OUT, s["id"] + ".geojson"), encoding="utf8"))["features"]
          if not f["geometry"] and f["properties"].get("ficha")}
for pag, rs in sorted(por_pag.items()):
    sids = sorted({sid_de.get(r["i"], "—") for r in rs})
    lin.append(f"| {pag} | {len(rs)} | {'; '.join(' · '.join(tit_de[s]) if s in tit_de else s for s in sids)} | "
               f"{sum(1 for r in rs if ficha(r) in sin_ub) or ''} |")
lin += ["", f"Recursos de la web sin subcapa: {len(faltan)}."]
open(os.path.join(BASE, "cobertura_web.md"), "w", encoding="utf8").write("\n".join(lin) + "\n")
os.makedirs(os.path.join(BASE, "build"), exist_ok=True)
open(os.path.join(BASE, "build", "emparejamientos.txt"), "w", encoding="utf8").write("\n".join(sorted(LOG_PARES)) + "\n")

tot = sum(s["n"] for g in CAT for s in g["subcapas"])
sin = sum(s["sin_ubicacion"] for g in CAT for s in g["subcapas"])
print(f"{len(CAT)} capas, {sum(len(g['subcapas']) for g in CAT)} subcapas, {tot} elementos en el mapa, {sin} sin ubicación")
