"""
Descarga del Registro de Turismo de Andalucía (API OpenRTA) los establecimientos de Marbella que usa
el visor, tipo a tipo (consultas pequeñas: las respuestas grandes se cortan desde GitHub).
Las viviendas de uso turístico (VUT) no se descargan: no forman parte del visor.

Escribe rta_marbella_no_vut.json. Si alguna consulta falla, conserva el fichero anterior.
Uso: python 00_descargar_rta.py
"""

import json, os, sys, time, urllib.parse, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(BASE, "rta_marbella_no_vut.json")
API = "https://datos.juntadeandalucia.es/api/v0/openrta/search"
TIPOS = ["Establecimiento Hotelero", "Apartamento turístico", "Casa rural", "Vivienda turística de alojamiento rural",
         "Empresa de turismo activo", "Oficina de turismo"]


def consulta(tipo):
    q = {"id": "-", "object_type": tipo, "category": "-", "group": "-", "modality": "-", "province": "-",
         "municipality": "MARBELLA", "order_by": "id", "mode": "ASC", "format": "json", "size": "3000"}
    for intento in range(5):
        try:
            req = urllib.request.Request(API + "?" + urllib.parse.urlencode(q),
                                         headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
            d = json.loads(urllib.request.urlopen(req, timeout=180).read().decode("utf-8"))
            if len(d["results"]) != d["total_hits"]:
                raise ValueError(f"respuesta incompleta ({len(d['results'])} de {d['total_hits']})")
            return d["results"]
        except Exception as e:
            print(f"  {tipo}: intento {intento + 1} fallido ({e})", flush=True)
            time.sleep(10 * (intento + 1))
    sys.exit(f"No se ha podido descargar «{tipo}» del RTA; se conserva el fichero anterior")


filas = []
for t in TIPOS:
    r = consulta(t)
    print(f"{t}: {len(r)}")
    filas += r
if len([r for r in filas if r["objects_type_id"] == "Establecimiento Hotelero"]) < 50:
    sys.exit("Registro sospechosamente corto; se conserva el fichero anterior")
json.dump(filas, open(SALIDA, "w", encoding="utf8"), ensure_ascii=False)
print(f"RTA de Marbella: {len(filas)} establecimientos")
