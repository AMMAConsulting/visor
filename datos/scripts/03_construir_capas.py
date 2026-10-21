"""
Construye las capas y subcapas del Visor de Turismo (SITMA) a partir de:
  - build/osm.pkl                  (OpenStreetMap, 02_leer_osm.py)
  - rta_marbella_no_vut.json       (Registro de Turismo de Andalucía, OpenRTA)
  - distinciones.json              (Guía MICHELIN y Guía Repsol, edición 2026)

Escribe en ../web/data/ un GeoJSON por subcapa y catalogo.json con la estructura de capas,
que lee el visor y del que salen también las tablas del documento Word.

Uso: python 03_construir_capas.py
"""

import json, os, pickle, re, time, unicodedata, urllib.parse, urllib.request
from datetime import date
from pyproj import Transformer
from shapely.geometry import Point, mapping
from shapely.ops import unary_union

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(os.path.dirname(BASE), "web")
OUT = os.path.join(WEB, "data")
os.makedirs(OUT, exist_ok=True)

osm = pickle.load(open(os.path.join(BASE, "build", "osm.pkl"), "rb"))
TERMINO, E = osm["termino"], osm["elementos"]
RTA = json.load(open(os.path.join(BASE, "rta_marbella_no_vut.json"), encoding="utf8"))
DIST = json.load(open(os.path.join(BASE, "distinciones.json"), encoding="utf8"))
utm = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)

F_OSM = "OpenStreetMap (ODbL)"
F_RTA = "Registro de Turismo de Andalucía (OpenRTA)"


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
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


def grupo(gid, titulo, color, descripcion):
    CAT.append({"id": gid, "titulo": titulo, "color": color, "descripcion": descripcion, "subcapas": []})


def sub(sid, titulo, feats, geometria, fuente, descripcion, color=None, pendiente=None, visible=False):
    fc = {"type": "FeatureCollection", "features": feats}
    json.dump(fc, open(os.path.join(OUT, sid + ".geojson"), "w", encoding="utf8"), ensure_ascii=False,
              separators=(",", ":"))
    CAT[-1]["subcapas"].append({"id": sid, "titulo": titulo, "n": len(feats), "geometria": geometria,
                                "fuente": fuente, "descripcion": descripcion, "color": color or CAT[-1]["color"],
                                "pendiente": pendiente, "visible": visible})
    print(f"  {sid:28s} {len(feats):5d}")


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


def cartociudad(direccion):
    if direccion in cache_geo:
        return cache_geo[direccion]
    q = urllib.parse.quote(direccion + ", Marbella")
    try:
        r = json.loads(urllib.request.urlopen(
            f"https://www.cartociudad.es/geocoder/api/geocoder/find?q={q}", timeout=30).read())
        res = [r["lng"], r["lat"]] if r.get("lat") and r.get("muni", "").lower() == "marbella" else None
    except Exception:
        res = None
    cache_geo[direccion] = res
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
    p = {"nombre": (r.get("name") or "").title(), "categoria": " · ".join(
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


# ================================================================================================
print("Construyendo capas...")

# 1. MAR -----------------------------------------------------------------------------------------
grupo("mar", "Mar", "#0E7FB8", "Litoral, playas, puertos y actividades náuticas.")

BANDERA = ["cabopino", "cable", "faro", "fontanilla", "nagueles", "casablanca", "monteros", "adelfas",
           "guadalmina", "san pedro", "venus", "bajadilla"]
playas = marcar(osm_sel(lambda e: T(e, "natural") == "beach", con_nombre=False))
fs = []
for e in playas:
    n = norm(nombre(e))
    if not n and e["g"].area < 2e-7:
        continue
    ba = any(b in n for b in BANDERA)
    fs.append(feat(e, props_osm(e, nombre=nombre(e) or "Playa (sin nombre en origen)",
                                bandera_azul="Sí (2026, ADEAC)" if ba else None)))
sub("playas", "Playas", fs, "polígono", F_OSM + "; Bandera Azul: ADEAC 2026",
    "Playas del término municipal. Atributo de Bandera Azul (ADEAC, temporada 2026).", visible=True)

puertos = marcar(osm_sel(lambda e: T(e, "leisure") == "marina" or T(e, "landuse") == "harbour" or T(e, "harbour")))
sub("puertos", "Puertos", [feat(e, props_osm(e)) for e in dedup(puertos)], "polígono", F_OSM,
    "Puertos deportivos y pesquero: José Banús, Virgen del Carmen, La Bajadilla y Cabopino.")

RE_CLUB = re.compile(r"beach club|club de playa|nikki beach|ocean club|puro beach|trocadero|la sala by the sea|"
                     r"nao pool|amare beach|playa padre|bounty beach|kova beach|amu beach", re.I)
clubes = marcar(dedup(osm_sel(lambda e: (RE_CLUB.search(nombre(e)) and (T(e, "amenity") or T(e, "leisure")))
                                     or (T(e, "leisure") == "beach_resort"))))
sub("clubes_playa", "Clubes de playa", [feat(e, props_osm(e), True) for e in clubes], "punto", F_OSM,
    "Clubes de playa (beach clubs) con restauración, hamacas y servicios.")

nautica = marcar(dedup(osm_sel(lambda e: T(e, "sport") in ("sailing", "scuba_diving", "surfing", "kitesurfing",
                                                             "water_ski", "canoe", "diving", "windsurfing",
                                                             "rowing", "motorboat")
                                         or T(e, "amenity") == "boat_rental" or T(e, "club") == "sailing"
                                         or T(e, "shop") in ("boat", "water_sports", "diving")
                                         or re.search(r"cableski|diving|buceo|jet ?ski|charter|paddle ?surf|sup", nombre(e), re.I))))
fs = [feat(e, props_osm(e), True) for e in nautica]
fs += rta(lambda r: r["objects_type_id"] == "Empresa de turismo activo" and re.search("diving|nautic|mar", r["name"], re.I),
          {"categoria": "Empresa de turismo activo"})
sub("actividades_nauticas", "Actividades náuticas", fs, "punto", F_OSM + "; " + F_RTA,
    "Clubes náuticos, escuelas de vela y buceo, alquiler de embarcaciones y empresas náuticas registradas.")

socorro = marcar(osm_sel(lambda e: T(e, "emergency") == "lifeguard" or T(e, "amenity") == "lifeguard"
                         or T(e, "emergency") == "lifeguard_base", con_nombre=False))
sub("salvamento", "Salvamento y socorrismo", [feat(e, props_osm(e, nombre=nombre(e) or "Puesto de socorrismo"), True)
                                              for e in socorro], "punto", F_OSM,
    "Puestos de salvamento y socorrismo en playa. Nueva: conviene completarla con el Plan de Playas municipal.",
    pendiente="Completar con el Plan de Salvamento y Socorrismo del Ayuntamiento (Playas)")

# 2. GOLF ----------------------------------------------------------------------------------------
grupo("golf", "Golf", "#3A8D3F", "Campos de golf y servicios al golfista.")
RE_ACADEMIA = re.compile(r"range|academ|school|escuela|lesson|driving|pitch ?& ?putt|practice", re.I)
academias = marcar(dedup(osm_sel(lambda e: (T(e, "golf") == "driving_range" or
                                            ((T(e, "leisure") == "golf_course" or T(e, "sport") == "golf")
                                             and RE_ACADEMIA.search(nombre(e)))) and T(e, "leisure") != "park")))
campos = marcar(dedup(osm_sel(lambda e: T(e, "leisure") == "golf_course" and nombre(e) not in ("Course A",))))
sub("campos_golf", "Campos de golf", [feat(e, props_osm(e)) for e in campos], "polígono", F_OSM,
    "Recintos de los campos de golf del término.")
sub("academias_golf", "Academias y escuelas de golf", [feat(e, props_osm(e), True) for e in academias], "punto",
    F_OSM, "Campos de prácticas (driving range), academias y escuelas.")
tiendas = marcar(osm_sel(lambda e: T(e, "shop") == "golf" or (T(e, "shop") and re.search("golf", nombre(e), re.I))))
sub("tiendas_golf", "Tiendas de golf", [feat(e, props_osm(e), True) for e in tiendas], "punto", F_OSM,
    "Tiendas especializadas (pro-shops y comercios).",
    pendiente="Sin datos abiertos suficientes: alta por la Delegación o los propios clubes")
alquiler = marcar(osm_sel(lambda e: re.search(r"golf", nombre(e), re.I) and re.search(r"rent|alquiler|hire", nombre(e), re.I)))
sub("alquiler_golf", "Alquiler de equipos de golf", [feat(e, props_osm(e), True) for e in alquiler], "punto", F_OSM,
    "Alquiler de palos, buggies y material.",
    pendiente="Sin datos abiertos: alta por la Delegación o los propios clubes")

# 3. GASTRONOMÍA ---------------------------------------------------------------------------------
grupo("gastronomia", "Gastronomía", "#C0392B", "Restauración, distinciones y producto local.")


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


sub("michelin", "Estrellas Michelin", distincion("Guía MICHELIN"), "punto", "Guía MICHELIN España 2026",
    "Restaurantes con Estrella MICHELIN (edición 2026).", color="#B3001B")
sub("repsol", "Soles Repsol", distincion("Guía Repsol"), "punto", "Guía Repsol 2026",
    "Restaurantes con Sol Repsol (edición 2026).", color="#E67E22")
for d in DIST:
    for e in E:
        if T(e, "amenity") in ("restaurant", "bar", "cafe") and Point(d["lonlat"]).distance(punto(e)["g"]) < 0.0008 \
                and norm(d["nombre"]).split()[0] in norm(nombre(e)):
            USADOS.add(e["id"])

chir = marcar(dedup(osm_sel(lambda e: T(e, "amenity") in ("restaurant", "bar", "cafe", "fast_food")
                                      and (cerca_playa(e) or re.search("chiringuito", nombre(e), re.I)))))
sub("chiringuitos", "Chiringuitos", [feat(e, props_osm(e, cocina=cocina(e["t"])), True) for e in chir],
    "punto", F_OSM, "Establecimientos de restauración sobre la arena o en el borde de la playa, o denominados chiringuito.")

rest = marcar(dedup(osm_sel(lambda e: T(e, "amenity") == "restaurant")))
sub("restaurantes", "Restaurantes", [feat(e, props_osm(e, cocina=cocina(e["t"])), True) for e in rest],
    "punto", F_OSM, "Resto de restaurantes del municipio. En la web se mostrará la selección de «restaurantes destacados».",
    pendiente="La web de Turismo usa «Restaurantes destacados»: la Delegación debe marcar cuáles lo son")

cat = marcar(osm_sel(lambda e: T(e, "craft") == "caterer" or T(e, "shop") == "caterer" or
                     re.search(r"catering", nombre(e), re.I)))
sub("catering", "Catering", [feat(e, props_osm(e), True) for e in cat], "punto", F_OSM,
    "Empresas de catering con sede en Marbella.", pendiente="Sin datos abiertos suficientes: alta por la Delegación")

vino = marcar(dedup(osm_sel(lambda e: T(e, "shop") == "wine" or T(e, "amenity") == "wine_bar" or
                            (T(e, "amenity") in ("bar", "pub") and re.search(r"vino|wine|vinoteca|bodega", nombre(e), re.I)))))
sub("vinotecas", "Vinotecas", [feat(e, props_osm(e), True) for e in vino], "punto", F_OSM,
    "Vinotecas, tiendas de vino y bares de vino.")
deli = marcar(dedup(osm_sel(lambda e: T(e, "shop") in ("deli", "cheese", "gourmet", "delicatessen") or
                            (T(e, "shop") and re.search(r"gourmet|delicatessen|ib[eé]ric", nombre(e), re.I)))))
sub("delicatessen", "Delicatessen", [feat(e, props_osm(e), True) for e in deli], "punto", F_OSM,
    "Tiendas gourmet y de producto selecto.")
merc = marcar(dedup(osm_sel(lambda e: T(e, "amenity") == "marketplace" and re.search(r"mercado", nombre(e), re.I))))
sub("mercados", "Mercados de abastos", [feat(e, props_osm(e), True) for e in merc], "punto", F_OSM,
    "Mercados municipales de abastos (producto fresco y local). Nueva.")

# 4. ALOJAMIENTOS --------------------------------------------------------------------------------
grupo("alojamientos", "Alojamientos", "#7D3C98", "Establecimientos de alojamiento turístico reglado (RTA).")
H = lambda g: (lambda r: r["objects_type_id"] == "Establecimiento Hotelero" and r.get("group") == g)
sub("hoteles", "Hoteles", rta(H("Hotel")), "punto", F_RTA, "Hoteles de 1 a 5 estrellas y Gran Lujo.")
sub("hoteles_apartamento", "Hoteles-apartamento", rta(H("Hotel-Apartamento")), "punto", F_RTA,
    "Hoteles-apartamento de 2 a 4 estrellas.")
sub("hostales", "Hostales", rta(H("Hostal")), "punto", F_RTA, "Hostales de 1 y 2 estrellas.")
sub("pensiones", "Pensiones", rta(H("Pensión")), "punto", F_RTA, "Pensiones.")
sub("apartamentos", "Apartamentos turísticos", rta(lambda r: r["objects_type_id"] == "Apartamento turístico"),
    "punto", F_RTA, "Apartamentos turísticos en edificio/complejo o conjunto (1 a 3 llaves). Nueva.")
sub("rural", "Alojamiento rural", rta(lambda r: r["objects_type_id"] in ("Casa rural",
                                                                         "Vivienda turística de alojamiento rural")),
    "punto", F_RTA, "Casas rurales y viviendas turísticas de alojamiento rural. Nueva.")
alb = marcar(osm_sel(lambda e: T(e, "tourism") == "hostel" and re.search(r"albergue|hostel|youth", nombre(e), re.I)))
sub("albergues", "Albergues", [feat(e, props_osm(e), True) for e in alb], "punto", F_OSM,
    "Albergues (incluido el Albergue Inturjoven de Marbella).",
    pendiente="El RTA no publica albergues de Marbella: contrastar con Inturjoven")
camp = marcar(osm_sel(lambda e: T(e, "tourism") == "camp_site"))
sub("campings", "Campings", [feat(e, props_osm(e)) for e in camp], "polígono", F_OSM,
    "Campamentos de turismo.", pendiente="El RTA no publica campings de Marbella: contrastar con el registro")

# 5. NATURALEZA ----------------------------------------------------------------------------------
grupo("naturaleza", "Naturaleza", "#2E7D32", "Espacios naturales, sierra, parques y grandes senderos.")
prot = marcar(osm_sel(lambda e: (T(e, "boundary") == "protected_area" or T(e, "leisure") == "nature_reserve")
                      and e["g"].geom_type != "Point"))
sub("espacios_protegidos", "Espacios naturales protegidos", [feat(e, props_osm(e)) for e in prot], "polígono",
    F_OSM + "; REDIAM (servicio WMS)", "Monumento Natural Dunas de Artola (Cabopino) y Red Natura 2000 "
                                       "(capa oficial de la REDIAM superpuesta).")
cumbres = marcar(osm_sel(lambda e: T(e, "natural") in ("peak", "saddle")))
sub("cumbres", "Sierra Blanca y cumbres", [feat(e, props_osm(e, altitud=(T(e, "ele") + " m") if T(e, "ele") else None))
                                           for e in cumbres], "punto", F_OSM,
    "Picos de Sierra Blanca: La Concha, Cerro Torrón, Pico del Águila…")
mir = marcar(osm_sel(lambda e: T(e, "tourism") == "viewpoint"))
sub("miradores", "Miradores", [feat(e, props_osm(e), True) for e in mir], "punto", F_OSM,
    "Miradores con nombre. Nueva.")
lago = marcar(osm_sel(lambda e: re.search(r"tortugas", nombre(e), re.I) and e["g"].geom_type != "Point"))
lago = lago or marcar(osm_sel(lambda e: re.search(r"tortugas", nombre(e), re.I)))
sub("lago_tortugas", "Lago de las Tortugas", [feat(e, props_osm(e, otros_nombres="Embalse Viejo")) for e in lago],
    "polígono", F_OSM, "Lago de las Tortugas, antiguamente denominado Embalse Viejo.")
parq = marcar(dedup(osm_sel(lambda e: T(e, "leisure") in ("park", "garden") and e["g"].geom_type != "Point"
                            and not re.search(r"golf|beach", nombre(e), re.I))))
sub("parques", "Parques y jardines", [feat(e, props_osm(e)) for e in parq], "polígono", F_OSM,
    "Parques urbanos y jardines con nombre (Alameda, Arboretum, La Represa, El Mirador…).")


def ruta(cond):
    return [e for e in E if e["t"].get("type") == "route" and cond(e["t"])]


senda = ruta(lambda t: "senda litoral" in norm(t.get("name")))
sub("senda_litoral", "Senda Litoral", [feat(e, props_osm(e, ref=T(e, "ref")), False) for e in senda], "línea",
    F_OSM, "Senda Litoral de la provincia de Málaga a su paso por Marbella (también señalizada como GR 92).",
    color="#0097A7")
gr = ruta(lambda t: t.get("ref", "").replace("-", " ").startswith("GR 249"))
sub("gr249", "Gran Senda de Málaga (GR-249)",
    [feat(e, props_osm(e, ref=T(e, "ref"), etapa=nombre(e)), False) for e in gr], "línea", F_OSM,
    "Etapas Estepona–Marbella y Marbella–Ojén de la Gran Senda de Málaga.", color="#D84315")
sen = ruta(lambda t: t.get("route") == "hiking" and not t.get("ref", "").replace("-", " ").startswith(("GR 249", "GR 92"))
           and "senda litoral" not in norm(t.get("name")))
sub("senderos", "Otros senderos (PR-A y locales)", [feat(e, props_osm(e, ref=T(e, "ref")), False) for e in sen],
    "línea", F_OSM, "Senderos de pequeño recorrido de Sierra Blanca (PR-A 135, 140, 168, 169) y rutas locales. Nueva.",
    color="#6D4C41")

# 6. TURISMO ACTIVO Y CICLOTURISMO ---------------------------------------------------------------
grupo("activo", "Turismo activo y cicloturismo", "#F39C12",
      "Epígrafe propio: empresas de turismo activo, rutas ciclistas y alquiler de bicicletas.")
bici = [e for e in E if T(e, "highway") == "cycleway" and e["g"].geom_type in ("LineString", "MultiLineString")]
sub("carriles_bici", "Carriles bici", [feat(e, props_osm(e, nombre=nombre(e) or "Carril bici"), False) for e in bici],
    "línea", F_OSM, "Red de carriles bici urbanos y del paseo marítimo.", color="#F39C12")
btt = ruta(lambda t: t.get("route") in ("bicycle", "mtb"))
sub("rutas_ciclistas", "Rutas cicloturistas y BTT", [feat(e, props_osm(e, ref=T(e, "ref")), False) for e in btt],
    "línea", F_OSM, "Rutas ciclistas señalizadas (red CIMA de la Costa del Sol Occidental, BTT).", color="#AF601A")
alqb = marcar(osm_sel(lambda e: T(e, "amenity") == "bicycle_rental" or T(e, "shop") == "bicycle"))
sub("alquiler_bicis", "Alquiler y tiendas de bicicletas", [feat(e, props_osm(e), True) for e in alqb], "punto", F_OSM,
    "Alquiler, reparación y venta de bicicletas.")
ta = rta(lambda r: r["objects_type_id"] == "Empresa de turismo activo" and not re.search("diving|nautic", r["name"], re.I), {"categoria": "Empresa de turismo activo"})
sub("turismo_activo", "Empresas de turismo activo", ta, "punto", F_RTA,
    "Empresas de turismo activo inscritas en el RTA con sede o base en Marbella.",
    pendiente="El RTA solo recoge las empresas con domicilio en Marbella: añadir las que operan en el término")

# 7. CULTURA Y PATRIMONIO ------------------------------------------------------------------------
grupo("cultura", "Cultura y patrimonio", "#8E5B3E", "Nueva: patrimonio histórico, museos, escena cultural y arte urbano.")
arq = marcar(osm_sel(lambda e: T(e, "historic") == "archaeological_site" or
                     re.search(r"romana|romanas|paleocristiana|bóvedas", nombre(e), re.I)))
sub("arqueologia", "Patrimonio arqueológico", [feat(e, props_osm(e), True) for e in dedup(arq)], "punto", F_OSM,
    "Villa romana de Río Verde, Termas romanas de Las Bóvedas, Basílica paleocristiana de Vega del Mar.")
mon = marcar(dedup(osm_sel(lambda e: T(e, "historic") in ("castle", "fort", "tower", "city_gate", "ruins", "building",
                                                          "monument", "manor", "watermill", "mine", "house",
                                                          "church", "monastery", "wayside_cross", "boundary_stone")
                           or T(e, "man_made") == "watchtower" or re.search(r"torre (almenara|vig)", nombre(e), re.I))))
sub("monumentos", "Monumentos y edificios históricos", [feat(e, props_osm(e, tipo=T(e, "historic")), True) for e in mon],
    "punto", F_OSM, "Castillo, torres almenaras, Fuerte de San Luis, Hospital Bazán, Casa del Corregidor, Trapiche del Prado…")
rel = marcar(dedup(osm_sel(lambda e: T(e, "amenity") == "place_of_worship" and
                           re.search(r"iglesia|ermita|capilla|parroquia|convento|santuario|mezquita|templo",
                                     nombre(e), re.I))))
sub("patrimonio_religioso", "Patrimonio religioso", [feat(e, props_osm(e), True) for e in rel], "punto", F_OSM,
    "Iglesias, ermitas y templos con interés turístico (Iglesia de la Encarnación, ermitas, Mezquita del Rey Fahd…).")
mus = marcar(dedup(osm_sel(lambda e: T(e, "tourism") in ("museum", "gallery"))))
sub("museos", "Museos y salas de exposiciones", [feat(e, props_osm(e), True) for e in mus], "punto", F_OSM,
    "Museo Ralli, Museo del Grabado Español Contemporáneo, Cortijo Miraflores, galerías.")
esc = marcar(dedup(osm_sel(lambda e: T(e, "amenity") in ("theatre", "arts_centre", "conference_centre",
                                                          "exhibition_centre", "community_centre")
                           and not re.search("asociaci|vecinal", nombre(e), re.I))))
sub("escena", "Teatros, auditorios y centros culturales", [feat(e, props_osm(e), True) for e in esc], "punto",
    F_OSM, "Teatro Ciudad de Marbella, Auditorio, Palacio de Congresos, Centro Cultural Hospital Real…")
art = marcar(dedup(osm_sel(lambda e: T(e, "tourism") == "artwork" or T(e, "historic") in ("memorial", "statue"))))
sub("arte_urbano", "Arte en la calle", [feat(e, props_osm(e, autor=T(e, "artist_name")), True) for e in art], "punto",
    F_OSM, "Esculturas y arte público: las diez esculturas de Dalí de la Avenida del Mar, monumentos y estatuas.")

# 8. COMPRAS Y OCIO ------------------------------------------------------------------------------
grupo("ocio", "Compras y ocio", "#D81B60", "Nueva: comercio, ocio nocturno, cines y ocio familiar.")
mall = marcar(dedup(osm_sel(lambda e: T(e, "shop") in ("mall", "department_store"))))
sub("centros_comerciales", "Centros comerciales", [feat(e, props_osm(e), True) for e in mall], "punto", F_OSM,
    "Centros comerciales y grandes almacenes (La Cañada, Marina Banús, El Corte Inglés…).")
mdl = marcar(dedup(osm_sel(lambda e: T(e, "amenity") == "marketplace")))
sub("mercadillos", "Mercadillos", [feat(e, props_osm(e), True) for e in mdl], "punto", F_OSM,
    "Mercadillos semanales y mercados de artesanía.")
noc = marcar(dedup(osm_sel(lambda e: T(e, "amenity") in ("nightclub", "casino") or T(e, "leisure") == "dance")))
sub("ocio_nocturno", "Ocio nocturno y casinos", [feat(e, props_osm(e), True) for e in noc], "punto", F_OSM,
    "Discotecas, salas y casino.")
fam = marcar(dedup(osm_sel(lambda e: T(e, "leisure") in ("water_park", "amusement_arcade", "miniature_golf") or
                           T(e, "tourism") in ("theme_park", "zoo", "aquarium") or
                           re.search(r"funny beach|aventura|pirate|karting", nombre(e), re.I))))
sub("ocio_familiar", "Ocio familiar", [feat(e, props_osm(e), True) for e in fam], "punto", F_OSM,
    "Parques acuáticos, de aventura, karting, minigolf y ocio infantil.")
cin = marcar(dedup(osm_sel(lambda e: T(e, "amenity") == "cinema")))
sub("cines", "Cines", [feat(e, props_osm(e), True) for e in cin], "punto", F_OSM, "Salas de cine.")

# 9. INFORMACIÓN PRÁCTICA ------------------------------------------------------------------------
grupo("practica", "Información práctica", "#455A64", "Nueva: servicios al visitante.")
ofi = marcar(dedup(osm_sel(lambda e: T(e, "tourism") == "information" and T(e, "information") == "office")))
fs = [feat(e, props_osm(e), True) for e in ofi]
fs += [f for f in rta(lambda r: r["objects_type_id"] == "Oficina de turismo")
       if all(Point(f["geometry"]["coordinates"]).distance(punto(e)["g"]) > 0.001 for e in ofi)]
sub("oficinas_turismo", "Oficinas de turismo", fs, "punto", F_OSM + "; " + F_RTA,
    "Oficinas municipales de información turística.",
    pendiente="Confirmar con la Delegación la red actual de oficinas y puntos de información")
park = marcar(dedup(osm_sel(lambda e: T(e, "amenity") == "parking" and
                            (T(e, "parking") in ("underground", "multi-storey") or nombre(e)) and T(e, "access") not in ("private", "customers"))))
sub("aparcamientos", "Aparcamientos", [feat(e, props_osm(e, tipo=T(e, "parking"), plazas=T(e, "capacity")), True) for e in park],
    "punto", F_OSM, "Aparcamientos públicos y subterráneos.")
bus = marcar(dedup(osm_sel(lambda e: T(e, "amenity") == "bus_station")))
sub("estacion_autobuses", "Estación de autobuses", [feat(e, props_osm(e), True) for e in bus], "punto", F_OSM,
    "Estación de autobuses interurbanos.")
taxi = marcar(osm_sel(lambda e: T(e, "amenity") == "taxi", con_nombre=False))
sub("taxis", "Paradas de taxi", [feat(e, props_osm(e, nombre=nombre(e) or "Parada de taxi"), True) for e in taxi],
    "punto", F_OSM, "Paradas de taxi.")
rec = marcar(osm_sel(lambda e: T(e, "amenity") == "charging_station", con_nombre=False))
sub("recarga", "Puntos de recarga eléctrica", [feat(e, props_osm(e, nombre=nombre(e) or T(e, "operator") or "Punto de recarga"), True)
                                                for e in rec], "punto", F_OSM, "Puntos de recarga de vehículo eléctrico.",
    pendiente="Completar con el Punto de Acceso Nacional de recarga (MITMA/DGT)")
far = marcar(osm_sel(lambda e: T(e, "amenity") == "pharmacy", con_nombre=False))
sub("farmacias", "Farmacias", [feat(e, props_osm(e, nombre=nombre(e) or "Farmacia"), True) for e in far], "punto",
    F_OSM, "Farmacias.")
sal = marcar(dedup(osm_sel(lambda e: T(e, "amenity") == "hospital" or
                           (T(e, "amenity") in ("clinic", "doctors") and re.search(r"centro de salud|urgencia|hospital|consultorio", nombre(e), re.I)))))
sub("salud", "Hospitales y centros de salud", [feat(e, props_osm(e), True) for e in sal], "punto", F_OSM,
    "Hospitales, urgencias y centros de salud públicos y privados.")
pol = marcar(dedup(osm_sel(lambda e: T(e, "amenity") == "police", con_nombre=False)))
sub("policia", "Policía", [feat(e, props_osm(e, nombre=nombre(e) or "Policía"), True) for e in pol], "punto", F_OSM,
    "Policía Local, Policía Nacional y Guardia Civil.")
ase = marcar(osm_sel(lambda e: T(e, "amenity") == "toilets", con_nombre=False))
sub("aseos", "Aseos públicos", [feat(e, props_osm(e, nombre=nombre(e) or "Aseo público",
                                                  accesible="Sí" if T(e, "wheelchair") == "yes" else None), True) for e in ase],
    "punto", F_OSM, "Aseos públicos (incluidos los de playa).")

# -- término y catálogo ----------------------------------------------------------------------------
json.dump({"type": "Feature", "properties": {"nombre": "Término municipal de Marbella"},
           "geometry": geom({"g": TERMINO}, 0.0001)}, open(os.path.join(OUT, "termino.geojson"), "w"), separators=(",", ":"))
json.dump(cache_geo, open(CACHE_GEO, "w", encoding="utf8"), ensure_ascii=False, indent=1)

# orden de la propuesta inicial de la Delegación (Visor_Turismo_SITMA_v1) y, detrás, las subcapas nuevas
ORDEN = {
    "mar": ["actividades_nauticas", "playas", "puertos", "clubes_playa", "salvamento"],
    "golf": ["campos_golf", "academias_golf", "tiendas_golf", "alquiler_golf"],
    "gastronomia": ["michelin", "repsol", "restaurantes", "chiringuitos", "catering", "vinotecas", "delicatessen",
                    "mercados"],
    "alojamientos": ["hoteles", "hoteles_apartamento", "hostales", "pensiones", "albergues", "campings",
                     "apartamentos", "rural"],
    "naturaleza": ["espacios_protegidos", "cumbres", "lago_tortugas", "parques", "senda_litoral", "gr249",
                   "miradores", "senderos"],
}
PROPUESTA_V1 = {s for g in ORDEN.values() for s in g} - {"salvamento", "mercados", "apartamentos", "rural",
                                                          "miradores", "senderos"}
PROPUESTA_V1 |= {"carriles_bici", "rutas_ciclistas", "turismo_activo"}
for g in CAT:
    if g["id"] in ORDEN:
        g["subcapas"].sort(key=lambda s: ORDEN[g["id"]].index(s["id"]))
    d = g["descripcion"].replace("Nueva: ", "")
    g["descripcion"] = d[:1].upper() + d[1:]
    for s in g["subcapas"]:
        s["nueva"] = s["id"] not in PROPUESTA_V1
        s["descripcion"] = re.sub(r"\.? Nueva(:[^.]*)?\.", ".", s["descripcion"]).replace(" Nueva.", "")
    g["nueva"] = g["id"] not in ORDEN and g["id"] != "activo"
json.dump({"generado": date.today().isoformat(), "grupos": CAT}, open(os.path.join(OUT, "catalogo.json"), "w",
                                                                      encoding="utf8"), ensure_ascii=False, indent=1)
tot = sum(s["n"] for g in CAT for s in g["subcapas"])
print(f"{len(CAT)} capas, {sum(len(g['subcapas']) for g in CAT)} subcapas, {tot} elementos")
