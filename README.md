# Visor

Visor de AMMA Consulting con los recursos de Marbella: Mar, Golf, Gastronomía, Alojamientos, Naturaleza,
Turismo activo y cicloturismo, Cultura y patrimonio, Compras y ocio e Información práctica
(9 capas y 57 subcapas sobre ortofoto PNOA).

Web: https://ammaconsulting.github.io/visor/

## Estructura

| Carpeta | Contenido |
|---|---|
| `web/` | El visor (Leaflet). `data/catalogo.json` describe capas y subcapas; un GeoJSON por subcapa |
| `datos/scripts/` | Generación de los datos (ver abajo) |
| `datos/distinciones.json` | Restaurantes con Estrella MICHELIN y Sol Repsol (edición 2026), mantenido a mano |
| `datos/rta_marbella_no_vut.json` | Copia del Registro de Turismo de Andalucía (sin VUT) |
| `datos/geocodificacion.json` | Caché de direcciones geocodificadas con CartoCiudad |

## Datos

1. `00_descargar_rta.py`: alojamientos, turismo activo y oficinas de turismo desde la API OpenRTA.
2. `01_recortar_osm.py`: recorta el extracto de Andalucía de OpenStreetMap (Geofabrik) a Marbella.
3. `02_leer_osm.py`: monta puntos, áreas y rutas (GR 249, Senda Litoral, PR-A) dentro del término.
4. `03_construir_capas.py`: clasifica en subcapas y escribe `web/data/`.

La Action `datos.yml` lo repite el día 3 de cada mes y publica el resultado (`pages.yml`).
En local: descarga `andalucia-latest.osm.pbf` en `datos/build/` y ejecuta los cuatro scripts en orden.

Para cambiar una distinción gastronómica, edita `datos/distinciones.json` y ejecuta `03_construir_capas.py`.

## Licencias de los datos

OpenStreetMap © colaboradores de OpenStreetMap (ODbL) · RTA, REDIAM © Junta de Andalucía ·
PNOA, IGN Base, MTN © Instituto Geográfico Nacional (CC BY 4.0) · Guía MICHELIN, Guía Repsol (listas públicas, 2026) ·
Bandera Azul: ADEAC 2026.
