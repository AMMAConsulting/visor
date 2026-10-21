# Visor

Visor de AMMA Consulting con los recursos de Marbella sobre ortofoto PNOA: 15 capas y 111 subcapas.

Web: https://ammaconsulting.github.io/visor/

Las capas y subcapas siguen el directorio de recursos de turismo.marbella.es (Mar, Golf, Gastronomía,
Alojamientos, Naturaleza, Compras, Cultura, Deporte, Salud y bienestar, Ocio, Viajar con mascotas, Servicios
turísticos, Marbella de boda, Congresos y empresas e Información práctica), con los mismos nombres y en el mismo
orden. Todos los recursos que publica la web están en el visor; detrás de las categorías de la web, cada capa
tiene «otras subcapas» con información de fuentes abiertas (otros restaurantes, miradores, carriles bici,
patrimonio religioso, farmacias…).

## Estructura

| Carpeta | Contenido |
|---|---|
| `web/` | El visor (Leaflet). `data/catalogo.json` describe capas y subcapas; un GeoJSON por subcapa |
| `datos/scripts/` | Generación de los datos (ver abajo) |
| `datos/web_turismo.json` | Copia del directorio de recursos de turismo.marbella.es |
| `datos/cobertura_web.md` | Qué subcapa del visor recoge cada página de la web; se regenera con los datos |
| `datos/distinciones.json` | Restaurantes con Estrella MICHELIN y Sol Repsol (edición 2026), mantenido a mano |
| `datos/rta_marbella_no_vut.json` | Copia del Registro de Turismo de Andalucía (sin VUT) |
| `datos/geocodificacion.json` | Caché de direcciones geocodificadas con CartoCiudad |

## Datos

1. `00_descargar_rta.py`: alojamientos, turismo activo y oficinas de turismo desde la API OpenRTA.
2. `00b_descargar_web.py`: recorre el menú de turismo.marbella.es y guarda cada recurso con su categoría,
   coordenadas, dirección, imagen y ficha.
3. `01_recortar_osm.py`: recorta el extracto de Andalucía de OpenStreetMap (Geofabrik) a Marbella.
4. `02_leer_osm.py`: monta puntos, áreas y rutas (GR 249, Senda Litoral, PR-A) dentro del término.
5. `03_construir_capas.py`: monta el árbol de la web, une cada recurso con su entidad de OSM o del RTA
   (geometría y atributos) y escribe `web/data/` y `datos/cobertura_web.md`. Si la web publica una categoría
   nueva que el visor no tiene asignada, sus recursos van a la capa «Otros recursos de la web» y el
   informe lo indica.

La Action `datos.yml` lo repite el día 3 de cada mes y publica el resultado (`pages.yml`).
En local: descarga `andalucia-latest.osm.pbf` en `datos/build/` y ejecuta los scripts en orden.

Para cambiar una distinción gastronómica, edita `datos/distinciones.json` y ejecuta `03_construir_capas.py`.

## Licencias de los datos

Recursos turísticos: turismo.marbella.es (Ayuntamiento de Marbella) · OpenStreetMap © colaboradores de
OpenStreetMap (ODbL) · RTA, REDIAM © Junta de Andalucía · PNOA, IGN Base, MTN © Instituto Geográfico Nacional
(CC BY 4.0) · CartoCiudad (IGN) · Guía MICHELIN, Guía Repsol (listas públicas, 2026) · Bandera Azul: ADEAC 2026.
