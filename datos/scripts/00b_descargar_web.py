"""Descarga el directorio de recursos de turismo.marbella.es.

Recorre el menú de la web (Descubre, Vive, Servicios, Área profesional), lee los marcadores
de mapa de cada página (MapManager.addMarker) y escribe datos/web_turismo.json con un registro
por recurso y categoría. Si una página enlaza fichas que no tienen marcador, baja a esas fichas.
"""
import html
import json
import re
import sys
import time
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = "https://turismo.marbella.es"
RAIZ = Path(__file__).resolve().parents[1]
CACHE = RAIZ / "build" / "web"
SALIDA = RAIZ / "web_turismo.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}

# Secciones del menú cuyas páginas se recorren; no se entra en agenda, prensa ni zonas de usuario
SECCIONES = ("/descubre", "/vive", "/servicios", "/area-profesional")
NO_ENTRAR = ("/agenda", "/noticias", "/component/", "/area-profesional/galerias", "/area-profesional/videos",
             "/area-profesional/identidad", "/area-profesional/dti", "/area-profesional/planes",
             "/area-profesional/material", "/area-profesional/carta", "/descubre/historia",
             "/descubre/tradicion", "/descubre/sobre-marbella", "/descubre/como-llegar")
PROFUNDIDAD_MAX = 5
# páginas que repiten otra (dirección antigua) o que no presentan recursos sino apartados de texto
DUPLICADAS = {"/area-profesional/congresos-y-eventos.html", "/servicios/oficinas-de-informacion.html",
              "/servicios/marbella-film-office.html"}


def norm(t):
    t = unicodedata.normalize("NFKD", html.unescape(t or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def bajar(ruta, intentos=4):
    f = CACHE / (ruta.strip("/").replace("/", "_") or "inicio")
    if f.exists() and f.stat().st_size > 20000:
        return f.read_text(encoding="utf-8", errors="replace")
    for i in range(intentos):
        try:
            r = urllib.request.urlopen(urllib.request.Request(BASE + ruta, headers=UA), timeout=300)
            s = r.read().decode("utf-8", "replace")
            f.write_text(s, encoding="utf-8")
            return s
        except Exception as e:  # la web es lenta y a veces corta
            print(f"  reintento {i + 1} {ruta}: {e}", flush=True)
            time.sleep(5 * (i + 1))
    return ""


def campo(bloque, nombre):
    m = re.search(nombre + r"\s*:\s*'((?:[^'\\]|\\.)*)'", bloque)
    return m.group(1) if m else ""


def marcadores(s):
    out = []
    for b in re.findall(r"MapManager\.addMarker\(\{(.*?)\}\);", s, re.S):
        c = campo(b, "coordenadas")
        t = html.unescape(campo(b, "title")).strip()
        if not t:
            continue
        lat = lon = None
        m = re.match(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", c)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
        art = re.search(r"[?&]id=(\d+)", campo(b, "link"))
        dire = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", campo(b, "content"))).split())
        img = campo(b, "image").split("#")[0]
        out.append({"titulo": t, "lat": lat, "lon": lon, "articulo": art.group(1) if art else None,
                    "direccion": dire or None, "etiqueta": html.unescape(campo(b, "category")),
                    "imagen": BASE + img if img else None})
    return out


def kmls(s):
    return sorted({k for k in re.findall(r"loadKml\('([^']+)'", s) if k})


def hijos(s, ruta):
    """Enlaces a páginas que cuelgan de la ruta, con su rótulo."""
    base = ruta[:-5] + "/"
    out = {}
    for h, t in re.findall(r'href="(' + re.escape(base) + r'[^"#?]+\.html)"[^>]*aria-label="([^"]*)"', s):
        t = html.unescape(t)
        if t.lower() in ("más información", "descubrir", "mas informacion"):
            t = ""
        if t.startswith("logo-"):
            t = t[5:]
        if t or h not in out:
            out[h] = t or out.get(h, "")
    # rótulos de las fichas de servicios: logo-<nombre> en la misma tarjeta que el enlace
    for h, t in re.findall(r'href="(' + re.escape(base) + r'[^"#?]+\.html)"[^>]*>\s*<img[^>]*alt="([^"]*)"', s):
        out[h] = out.get(h) or html.unescape(t)
    return out


def rotulo(s):
    m = re.search(r"<title>([^<]*)</title>", s)
    t = html.unescape(m.group(1)).split(" - ")[0].strip() if m else ""
    return t


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    portada = bajar("/")
    menu = sorted({h for h in re.findall(r'href="(/[a-z0-9\-/]+\.html)"', portada)
                   if h.startswith(SECCIONES) and h.count("/") == 2 and not h.startswith(NO_ENTRAR)})
    print(len(menu), "páginas de menú", flush=True)

    registros, rutas_kml, visitadas, cruzados = [], {}, set(), {}
    cola = [(r, 1) for r in menu]
    with ThreadPoolExecutor(8) as ex:
        while cola:
            lote = [(r, p) for r, p in cola if r not in visitadas]
            cola = []
            for r, _ in lote:
                visitadas.add(r)
            for (ruta, prof), s in zip(lote, ex.map(lambda x: bajar(x[0]), lote)):
                if not s:
                    print("SIN RESPUESTA", ruta, flush=True)
                    continue
                partes = ruta[:-5].strip("/").split("/")
                ms = marcadores(s)
                for m in ms:
                    m.update(seccion=partes[0], categoria="/".join(partes[1:2]), pagina=ruta, pagina_titulo=rotulo(s))
                registros.extend(ms)
                if not ms:
                    # páginas que solo enlazan fichas de otras categorías (Soles Repsol, Excelencia)
                    base = ruta[:-5] + "/"
                    cruzados[ruta] = (rotulo(s), [html.unescape(t) for h, t in re.findall(
                        r'href="(/(?:vive|servicios)/[^"#?]+\.html)"[^>]*aria-label="([^"]*)"', s)
                        if not h.startswith(base) and h.count("/") >= 3])
                for k in kmls(s):
                    rutas_kml.setdefault(k, ruta)
                if prof >= PROFUNDIDAD_MAX:
                    continue
                titulos = {norm(m["titulo"]) for m in ms}
                for h, t in hijos(s, ruta).items():
                    if h in visitadas or h.startswith(NO_ENTRAR):
                        continue
                    # en el menú (prof 1) se entra en todas las categorías; más abajo, solo en
                    # las fichas que no traen marcador en la página que las lista
                    if prof == 1 or not t or norm(t) not in titulos:
                        cola.append((h, prof + 1))
            print(f"  {len(visitadas)} páginas, {len(registros)} marcadores", flush=True)

    for k, ruta in rutas_kml.items():
        url = k if k.startswith("http") else BASE + k
        destino = CACHE / ("kml_" + re.sub(r"[^A-Za-z0-9.]+", "_", k)[-80:])
        try:
            destino.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read())
        except Exception as e:
            print("KML no descargado", url, e)

    por_titulo = {}
    for r in registros:
        por_titulo.setdefault(norm(r["titulo"]), r)
    for ruta, (rot, titulos) in cruzados.items():
        partes = ruta[:-5].strip("/").split("/")
        for t in titulos:
            if norm(t) in por_titulo:
                registros.append({**por_titulo[norm(t)], "seccion": partes[0], "categoria": "/".join(partes[1:2]),
                                  "pagina": ruta, "pagina_titulo": rot})

    # una fila por recurso y página (un mismo recurso puede salir en varias categorías); en las
    # páginas que agrupan categorías se quitan los recursos que ya están en alguna de ellas
    vistos, unicos = set(), []
    for r in registros:
        k = (r["pagina"], norm(r["titulo"]))
        if k not in vistos:
            vistos.add(k)
            unicos.append(r)
    debajo = {}
    for r in unicos:
        partes = r["pagina"][:-5].split("/")
        for i in range(2, len(partes)):
            debajo.setdefault("/".join(partes[:i]), set()).add(norm(r["titulo"]))
    unicos = [r for r in unicos if r["pagina"] not in DUPLICADAS
              and norm(r["titulo"]) not in debajo.get(r["pagina"][:-5], set())]
    if len(unicos) < 800:
        sys.exit(f"Solo {len(unicos)} recursos: la web no respondió bien; se conserva la copia anterior")
    SALIDA.write_text(json.dumps({"recursos": unicos, "kml": rutas_kml}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(unicos), "recursos ->", SALIDA)


if __name__ == "__main__":
    main()
