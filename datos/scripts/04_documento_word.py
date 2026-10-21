"""
Genera «Visor de Turismo SITMA - Estructura de capas y subcapas (formato AMMA).docx» con el formato
corporativo de AMMA Consulting. Las cifras de cada subcapa salen de web/data/catalogo.json.

Uso: python 04_documento_word.py <carpeta_capturas>
"""

import json, os, sys
sys.path.insert(0, r"C:\Users\josem\.claude\skills\formato-amma-consulting\scripts")
from amma_docx import DocAMMA

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAP = sys.argv[1]
CAT = json.load(open(os.path.join(RAIZ, "web", "data", "catalogo.json"), encoding="utf8"))
G = {g["id"]: g for g in CAT["grupos"]}
S = {s["id"]: s for g in CAT["grupos"] for s in g["subcapas"]}
SALIDA = os.path.join(RAIZ, "Visor de Turismo SITMA - Estructura de capas y subcapas (formato AMMA).docx")
URL = "https://ammaconsulting.github.io/visor-turismo-sitma/"
N = lambda x: f"{x:,}".replace(",", ".")
total_sub = sum(len(g["subcapas"]) for g in CAT["grupos"])
total_el = sum(s["n"] for s in S.values())

d = DocAMMA(titulo=["VISOR DE TURISMO SITMA", "ESTRUCTURA DE CAPAS Y SUBCAPAS"],
            subtitulo="DELEGACIÓN DE TURISMO · AYUNTAMIENTO DE MARBELLA",
            fecha="Octubre, 2026", encabezado="VISOR DE TURISMO SITMA")


def numerada_nueva(items):
    """Lista numerada que empieza otra vez en 1 (numerada() de la plantilla continúa la anterior)."""
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    numbering = d.doc.part.numbering_part.element
    absid = numbering.xpath('//w:num[@w:numId="22"]/w:abstractNumId/@w:val')[0]
    nuevo = max(int(x) for x in numbering.xpath("//w:num/@w:numId")) + 1
    numbering.append(parse_xml(f'<w:num {nsdecls("w")} w:numId="{nuevo}"><w:abstractNumId w:val="{absid}"/>'
                               f'<w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>'))
    return d._lista(items, nuevo)


def cap(nombre):
    return os.path.join(CAP, nombre)


# =================================================================================================
d.h1("INTRODUCCIÓN")
d.h2("Objeto del documento")
d.p("El Ayuntamiento de Marbella va a incorporar al SITMA, su Sistema de Información Territorial, una nueva "
    "capa de Turismo. Este documento describe la estructura completa de esa capa: el mapa base, las capas "
    "temáticas y sus subcapas, el contenido y la geometría de cada una, los atributos que debe tener cada "
    "elemento, las fuentes de datos que la alimentan y quién debe mantenerla.")
d.p("Acompaña al documento un prototipo web funcional, construido con datos reales y abiertos, que permite "
    "ver la propuesta en funcionamiento antes de cargarla en el SITMA.")

d.h2("Punto de partida")
d.p("La Delegación de Turismo planteó una primera propuesta (Visor_Turismo_SITMA_v1) con estas premisas:")
d.vinetas([
    "Usar como mapa base la capa «Plano ciudad» del SITMA con una ortofoto de 2020, sobre la que se superponen "
    "las capas de información.",
    "Cada capa puede contener subcapas que se activan de forma individual.",
    "Las capas deben mantener el mismo orden y estructura de contenidos que la web de Turismo, para que el visor "
    "y la web sean homogéneos.",
    "Cinco capas: Mar, Golf, Gastronomía, Alojamientos y Naturaleza.",
    "Dos cuestiones abiertas: si es posible incorporar una cartografía además de la ortofoto, y si Cicloturismo "
    "y Turismo activo deben ir dentro de Naturaleza o en un epígrafe propio.",
])
d.p("Esta versión respeta íntegramente ese planteamiento —el orden y los nombres de las cinco capas y de sus "
    "subcapas se mantienen tal y como estaban— y lo completa: resuelve las dos cuestiones abiertas, añade las "
    "subcapas y capas que un visitante espera encontrar y concreta lo necesario para cargar los datos.")

d.h2("Criterios de diseño")
d.vinetas([
    "Correspondencia con la web de Turismo: cada capa equivale a una sección de la web y cada subcapa a un "
    "apartado. Cada elemento del mapa enlaza con su ficha en la web.",
    "Una subcapa, un tipo de recurso: no se mezclan establecimientos de distinta naturaleza en la misma subcapa.",
    "Geometría definida: cada subcapa es de puntos, de líneas o de polígonos. Una playa o un campo de golf se "
    "dibujan con su superficie; una ruta, con su trazado; un restaurante, con un punto.",
    "Datos oficiales o abiertos siempre que existan, y actualizables de forma automática. Lo que no publica "
    "ninguna fuente se identifica como «pendiente» y lo da de alta la Delegación.",
    "Sin duplicar el mantenimiento: una distinción (Estrella MICHELIN, Sol Repsol, Bandera Azul) es un atributo "
    "del establecimiento, aunque en el visor se muestre como subcapa.",
    "Pensado también para el móvil y en varios idiomas, como la web.",
])

# =================================================================================================
d.h1("MAPA BASE Y CAPAS DE REFERENCIA")
d.h2("Ortofoto")
d.p("La ortofoto de 2020 ya tiene seis años y no refleja cambios relevantes para el turismo: tramos nuevos de la "
    "Senda Litoral, regeneraciones de playa, hoteles y paseos nuevos. Se propone usar como fondo por defecto la "
    "ortofoto PNOA de máxima actualidad del Instituto Geográfico Nacional, que se renueva periódicamente sin "
    "coste ni descarga, y mantener la de 2020 como fondo alternativo.")
d.h2("Cartografía")
d.p("Sí es posible, y conviene. Sobre la ortofoto los nombres de calles y los símbolos se leen con dificultad, "
    "sobre todo en el móvil. El visor debe ofrecer un selector de fondo con, al menos, una ortofoto con nombres "
    "superpuestos, un callejero y un mapa topográfico (útil para Sierra Blanca y los senderos). En el SITMA, el "
    "callejero puede ser el propio «Plano ciudad» municipal; en el prototipo se usan los servicios del IGN.")
d.tabla([
    ["Fondo", "Servicio", "Uso"],
    ["Ortofoto actual (por defecto)", "IGN · PNOA máxima actualidad (WMTS) + nombres IGN Base Orto", "Vista general"],
    ["Ortofoto 2020", "IGN · PNOA histórico, capa PNOA2020 (WMS)", "Fondo de la propuesta inicial"],
    ["Callejero", "IGN Base (WMTS) o «Plano ciudad» del SITMA", "Localizar direcciones"],
    ["Topográfico", "IGN · Mapa Topográfico Nacional (WMTS)", "Naturaleza y senderos"],
], anchos_cm=[4.2, 7.3, 4.0])
d.h2("Capas de referencia")
d.p("Además de las capas turísticas, el visor ofrece capas de referencia que se pueden superponer: el límite del "
    "término municipal y, desde los servicios oficiales de la REDIAM (Junta de Andalucía), los espacios naturales "
    "protegidos y la Red Natura 2000. Se consultan en directo, de modo que siempre están al día.")

# =================================================================================================
d.h1("ESTRUCTURA DE CAPAS Y SUBCAPAS")
d.h2("Resumen")
d.p(f"La capa de Turismo queda organizada en {len(CAT['grupos'])} capas y {total_sub} subcapas. Las cinco "
    f"primeras son las de la web de Turismo, en su mismo orden; las cuatro siguientes son nuevas. El prototipo "
    f"carga {N(total_el)} elementos.")
filas = [["Capa", "Subcapas", "Elementos", "Origen"]]
for g in CAT["grupos"]:
    filas.append([g["titulo"], str(len(g["subcapas"])), N(sum(s["n"] for s in g["subcapas"])),
                  "Nueva" if g["nueva"] else ("Epígrafe propio (estaba en duda)" if g["id"] == "activo"
                                              else "Web de Turismo")])
filas.append([[("Total", {"negrita": True})], [(str(total_sub), {"negrita": True})],
              [(N(total_el), {"negrita": True})], ""])
d.tabla(filas, anchos_cm=[5.5, 2.5, 2.7, 4.8])
d.figura(cap("visor_todo.png"), "Prototipo del visor con subcapas de varias capas activas sobre la ortofoto",
         fuente="AMMA Consulting con datos de OSM, RTA, IGN y Guía MICHELIN/Repsol", ancho_cm=15)

d.h2("Cambios respecto a la propuesta inicial")
d.tabla([
    ["Cambio", "Motivo"],
    ["Cicloturismo y Turismo activo pasan a un epígrafe propio, «Turismo activo y cicloturismo»",
     "No son espacios naturales sino servicios (empresas registradas) y rutas; además, buena parte del "
     "cicloturismo es urbano (carriles bici, paseo marítimo)"],
    ["Dunas de Artola, Lago de las Tortugas y Campings pasan a ser subcapas",
     "En la propuesta eran los únicos elementos sin subcapa. Las Dunas se integran en «Espacios naturales "
     "protegidos», que admite otros espacios"],
    ["Estrellas MICHELIN y Soles Repsol se mantienen como subcapas, pero se generan como atributo",
     "Un mismo restaurante puede tener ambas distinciones (BACK y Messina las tienen) y cambian cada año: se "
     "registran una sola vez y el visor las muestra en su subcapa"],
    ["«Restaurantes destacados» se apoya en el censo completo de restaurantes",
     "La Delegación marca cuáles son destacados; el resto queda disponible para búsquedas"],
    ["Nuevas subcapas: Salvamento y socorrismo, Mercados de abastos, Apartamentos turísticos, Alojamiento "
     "rural, Miradores y Otros senderos",
     "Recursos que un visitante busca y que encajan en las capas existentes"],
    ["Nuevas capas: Cultura y patrimonio, Compras y ocio, Información práctica",
     "Patrimonio histórico, museos, ocio y servicios básicos (oficinas de turismo, aparcamientos, farmacias, "
     "salud) son contenidos habituales en un visor turístico"],
    ["Ortofoto actual por defecto y selector de fondos con cartografía", "Responde a la cuestión abierta"],
], anchos_cm=[7.0, 8.5])

d.h2("Árbol completo")
d.p("La tabla recoge todas las subcapas en el orden en que aparecen en el visor. Se marcan las nuevas y las que "
    "no tienen todavía datos abiertos y debe dar de alta la Delegación.")
filas = [["Capa", "Subcapa", "Geometría", "Elementos", "Estado"]]
for g in CAT["grupos"]:
    for i, s in enumerate(g["subcapas"]):
        estado = "Pendiente de alta" if s["pendiente"] and not s["n"] else ("Nueva" if s["nueva"] else "Propuesta v1")
        filas.append([g["titulo"] if i == 0 else "", s["titulo"], s["geometria"].capitalize(), N(s["n"]), estado])
d.tabla(filas, anchos_cm=[3.4, 5.4, 2.3, 2.0, 2.9], tam=10)

# =================================================================================================
d.h1("DESCRIPCIÓN DE LAS CAPAS")
d.p("Para cada capa se describe su contenido, las subcapas con su geometría y su fuente, y las observaciones "
    "relevantes para cargarla en el SITMA. La columna «Elementos» es la del prototipo a fecha de este documento.")

NOTAS = {
    "mar": [
        "Playas: polígono de la superficie de arena. Atributo Bandera Azul, que en la temporada 2026 tienen ocho "
        "playas de Marbella (Cabopino, El Cable, El Faro, La Fontanilla, Nagüeles-Casablanca, Los Monteros-Adelfas, "
        "San Pedro-Guadalmina y Venus-Bajadilla), según ADEAC. Se recomienda añadir atributos de accesibilidad, "
        "socorrismo, aseos, duchas y zona canina, que la Delegación de Playas ya gestiona.",
        "Clubes de playa y chiringuitos se distinguen por el servicio: el club de playa ofrece hamacas, piscina u "
        "otros servicios además de la restauración. El chiringuito se incluye en Gastronomía, como en la web.",
        "Salvamento y socorrismo es nueva: los puestos de socorro son información de seguridad que el visitante "
        "busca en la playa. Debe completarse con el plan de salvamento municipal de cada temporada.",
    ],
    "golf": [
        "Los campos de golf se dibujan con su recinto, lo que permite ver su extensión y su relación con las "
        "urbanizaciones. Se identifican 13 campos en el término.",
        "Tiendas de golf y Alquiler de equipos no tienen datos abiertos suficientes: la Delegación debe darlos de "
        "alta, previsiblemente a partir de los propios clubes (pro-shops) o de la Asociación de Campos de Golf.",
    ],
    "gastronomia": [
        "Estrellas MICHELIN (edición 2026): Skina (2 Estrellas), BACK, Messina y Nintai (1 Estrella).",
        "Soles Repsol (edición 2026): Areia, BACK (novedad), El Lago, Kava, La Milla, Leña, Lobito de Mar, Messina "
        "y Ta-Kumi, todos con 1 Sol según el listado publicado. Conviene confirmarlo con la Guía Repsol antes de "
        "publicar, igual que la ubicación exacta de La Milla y Lobito de Mar.",
        "Chiringuitos: establecimientos sobre la arena o en el borde de la playa. El Registro de Turismo de "
        "Andalucía recoge algunos, pero sin coordenadas.",
        "Catering no tiene datos abiertos: alta por la Delegación. Mercados de abastos (Mercado Central, San Pedro, "
        "Divina Pastora, Azalea) es nueva y conecta con la promoción del producto local.",
    ],
    "alojamientos": [
        "Se alimenta del Registro de Turismo de Andalucía (RTA), que da la categoría, el número de registro, las "
        "plazas y las coordenadas de cada establecimiento. Sigue la clasificación del Decreto 47/2004 de "
        "establecimientos hoteleros (hoteles, hoteles-apartamento, hostales y pensiones).",
        "Se añaden Apartamentos turísticos (Decreto 194/2010) y Alojamiento rural, que existen en el registro y "
        "son oferta reglada. Albergues y campings se toman de OpenStreetMap porque el RTA no publica ninguno en "
        "Marbella: hay que contrastarlos con Inturjoven y con el registro.",
        "Las viviendas de uso turístico (más de 15.700 en Marbella según el RTA) se dejan fuera a propósito: no son "
        "un recurso que se promocione por unidad y su inclusión es delicada. Si se quieren mostrar, que sea como "
        "mapa de densidad en un apartado de análisis, no como puntos.",
    ],
    "naturaleza": [
        "Espacios naturales protegidos incluye el Monumento Natural Dunas de Artola (Cabopino); la capa de "
        "referencia de la REDIAM añade la Red Natura 2000 de Sierra Blanca y el Parque Nacional Sierra de las "
        "Nieves, en el límite norte.",
        "Senda Litoral y Gran Senda de Málaga (GR-249) se dibujan con su trazado. La GR-249 atraviesa el término en "
        "dos etapas: Estepona–Marbella y Marbella–Ojén.",
        "Se añaden Miradores y Otros senderos (PR-A 135, 140, 168 y 169 de Sierra Blanca, Ruta de los Tres Valles, "
        "Vereda del Faro), que completan la oferta de naturaleza.",
    ],
    "activo": [
        "Resuelve la cuestión abierta de la propuesta: se crea un epígrafe propio. Si la web mantiene ambos "
        "contenidos dentro de Naturaleza, el visor puede seguirla sin cambiar los datos: solo cambia el árbol.",
        "Empresas de turismo activo: el RTA solo recoge las que tienen domicilio en Marbella. Las que operan en el "
        "término con sede en otro municipio deben añadirse.",
    ],
    "cultura": [
        "Patrimonio arqueológico: Villa romana de Río Verde, Termas romanas de Las Bóvedas y Basílica "
        "paleocristiana de Vega del Mar. Monumentos: Castillo, torres almenaras, Fuerte de San Luis, Hospital "
        "Bazán, Casa del Corregidor, Trapiche del Prado y otros.",
        "Arte en la calle recoge las esculturas de Dalí de la Avenida del Mar y el resto de arte público.",
        "Se recomienda contrastarla con la Guía Digital del Patrimonio Cultural de Andalucía (IAPH) y con la "
        "Delegación de Cultura.",
    ],
    "ocio": ["Centros comerciales, mercadillos, ocio nocturno y casino, ocio familiar y cines."],
    "practica": [
        "Servicios básicos al visitante. Oficinas de turismo es imprescindible y debe confirmarla la Delegación.",
        "Puntos de recarga puede completarse con el Punto de Acceso Nacional de datos de recarga.",
    ],
}

for g in CAT["grupos"]:
    d.h2(g["titulo"])
    d.p(g["descripcion"])
    filas = [["Subcapa", "Contenido", "Geom.", "Fuente", "Nº"]]
    for s in g["subcapas"]:
        filas.append([[(s["titulo"], {"negrita": True})] + ([(" (nueva)", {"cursiva": True})] if s["nueva"] else []),
                      s["descripcion"], s["geometria"].capitalize(),
                      s["fuente"].replace("OpenStreetMap (ODbL)", "OSM").replace(
                          "Registro de Turismo de Andalucía (OpenRTA)", "RTA"), N(s["n"])])
    d.tabla(filas, anchos_cm=[3.3, 6.2, 1.8, 3.2, 1.0], tam=9.5)
    if g["id"] in NOTAS:
        d.vinetas(NOTAS[g["id"]])
    if g["id"] == "naturaleza":
        d.figura(cap("visor_naturaleza.png"), "Capa Naturaleza sobre el mapa topográfico, con la Red Natura 2000 "
                 "de la REDIAM superpuesta", fuente="AMMA Consulting con datos de OSM, IGN y REDIAM", ancho_cm=15)
    if g["id"] == "gastronomia":
        d.figura(cap("visor_playa.png"), "Restaurantes, chiringuitos, clubes de playa y salvamento en La Fontanilla",
                 fuente="AMMA Consulting con datos de OSM e IGN", ancho_cm=15)

# =================================================================================================
d.h1("MODELO DE DATOS")
d.h2("Atributos comunes")
d.p("Todas las subcapas comparten un mismo conjunto de atributos, de modo que la ventana de información del "
    "visor es igual en todas y los datos se pueden reutilizar en la web, la app o el Observatorio Turístico.")
d.tabla([
    ["Campo", "Descripción", "Oblig."],
    ["id", "Identificador único y estable del elemento", "Sí"],
    ["capa / subcapa", "Código de la capa y de la subcapa (p. ej. mar / playas)", "Sí"],
    ["nombre", "Nombre oficial o comercial", "Sí"],
    ["descripcion_es / _en", "Texto breve en español e inglés (y demás idiomas de la web)", "Recom."],
    ["direccion", "Dirección postal normalizada (callejero municipal)", "Sí"],
    ["telefono, web, email", "Datos de contacto", "Recom."],
    ["url_ficha", "Enlace a la ficha del recurso en la web de Turismo", "Sí"],
    ["horario", "Horario de apertura (formato normalizado)", "Opcional"],
    ["accesibilidad", "Accesible para personas con movilidad reducida (sí / no / parcial)", "Recom."],
    ["foto", "Imagen principal (enlace a la web)", "Opcional"],
    ["fuente", "Origen del dato (RTA, OSM, Delegación…)", "Sí"],
    ["fecha_actualizacion", "Fecha de la última revisión del elemento", "Sí"],
], anchos_cm=[4.0, 9.5, 2.0])
d.h2("Atributos específicos")
d.tabla([
    ["Subcapa", "Atributos propios"],
    ["Playas", "Bandera Azul, longitud, tipo de arena, accesible, socorrismo, aseos, duchas, zona canina"],
    ["Puertos", "Número de amarres, eslora máxima, servicios"],
    ["Campos de golf", "Hoyos, par, diseñador, año de apertura"],
    ["Restauración", "Tipo de cocina, distinciones (MICHELIN, Repsol), precio medio"],
    ["Alojamientos", "Nº de registro RTA, categoría, plazas, unidades de alojamiento"],
    ["Senderos y rutas", "Código (GR, PR-A), longitud, desnivel, dificultad, duración, archivo GPX"],
    ["Patrimonio", "Época, protección (BIC, catalogado), horario de visita, precio"],
], anchos_cm=[4.0, 11.5])
d.h2("Ventana de información")
d.p("Al pulsar un elemento se abre una ventana con la capa y la subcapa, el nombre, los atributos disponibles, el "
    "enlace a la ficha de la web de Turismo y la fuente del dato. Si la ubicación es aproximada (por ejemplo, "
    "porque se ha obtenido a partir de la dirección), se avisa.")
d.figura(cap("visor_popup.png"), "Ventana de información de un restaurante con Estrella MICHELIN",
         fuente="AMMA Consulting con datos de la Guía MICHELIN 2026 e IGN", ancho_cm=14)
d.h2("Simbología")
d.p("Cada capa tiene un color y cada subcapa un icono propio dentro de ese color, para reconocer el tipo de "
    "recurso sin abrir la leyenda. Las líneas (senderos, carriles bici) y los polígonos (playas, golf, parques) "
    "llevan el color de su capa; los recursos con distinción gastronómica, un halo dorado.")
d.tabla([["Capa", "Color", "Capa", "Color"]] + [
    [a["titulo"], a["color"], b["titulo"] if b else "", b["color"] if b else ""]
    for a, b in zip(CAT["grupos"][0::2], CAT["grupos"][1::2] + [None])], anchos_cm=[5.0, 2.75, 5.0, 2.75])

# =================================================================================================
d.h1("FUENTES DE DATOS Y MANTENIMIENTO")
d.h2("Inventario de fuentes")
d.tabla([
    ["Fuente", "Organismo", "Contenido", "Acceso", "Actualización"],
    ["Registro de Turismo de Andalucía (OpenRTA)", "Junta de Andalucía", "Alojamientos, turismo activo, oficinas de "
     "turismo", "API JSON abierta", "Diaria"],
    ["OpenStreetMap", "Comunidad OSM (ODbL)", "Playas, puertos, golf, restauración, patrimonio, rutas, servicios",
     "Extracto Geofabrik", "Diaria"],
    ["PNOA, IGN Base, MTN", "Instituto Geográfico Nacional", "Ortofotos y cartografía base", "WMS / WMTS", "Periódica"],
    ["Espacios protegidos y Red Natura", "REDIAM (Junta de Andalucía)", "Límites oficiales", "WMS", "Periódica"],
    ["CartoCiudad", "IGN", "Geocodificación de direcciones", "API abierta", "Continua"],
    ["Guía MICHELIN", "Michelin", "Estrellas", "Web pública", "Anual (noviembre)"],
    ["Guía Repsol", "Repsol", "Soles", "Web pública", "Anual (febrero)"],
    ["Bandera Azul", "ADEAC", "Playas y puertos galardonados", "Web pública", "Anual (mayo)"],
    ["Delegación de Turismo y otras delegaciones", "Ayuntamiento", "Datos sin fuente abierta, «destacados», enlaces "
     "a la web", "Alta manual", "Continua"],
], anchos_cm=[3.6, 2.9, 4.0, 2.6, 2.4], tam=10)
d.h2("Responsables y periodicidad")
d.tabla([
    ["Capas o subcapas", "Responsable propuesto", "Revisión"],
    ["Alojamientos, turismo activo (RTA), OSM", "Automática (proceso mensual)", "Mensual"],
    ["Distinciones gastronómicas y Bandera Azul", "Delegación de Turismo", "Anual, tras cada edición"],
    ["Restaurantes destacados, enlaces a la web, textos e imágenes", "Delegación de Turismo", "Continua"],
    ["Playas, salvamento y servicios de playa", "Delegación de Playas", "Cada temporada"],
    ["Parques, espacios naturales y senderos", "Medio Ambiente / Parques y Jardines", "Anual"],
    ["Patrimonio, museos y escena cultural", "Delegación de Cultura", "Anual"],
    ["Mapa base, término y publicación", "SITMA", "Según el servicio"],
], anchos_cm=[6.5, 5.5, 3.5])
d.h2("Datos pendientes de alta")
d.p("Estas subcapas no tienen hoy una fuente abierta suficiente y requieren que la Delegación aporte los datos:")
d.vinetas([[(s["titulo"] + ": ", {"negrita": True}), (s["pendiente"][0].lower() + s["pendiente"][1:] + ".", {})]
           for s in S.values() if s["pendiente"]])

# =================================================================================================
d.h1("PROTOTIPO WEB")
d.h2("Descripción")
d.p("Para validar la estructura se ha construido un prototipo web que ya funciona con datos reales. Reproduce el "
    "comportamiento esperado del visor en el SITMA:")
d.vinetas([
    "Árbol de capas y subcapas en el orden de la web de Turismo, con casilla por subcapa y por capa completa, "
    "y el número de elementos de cada una.",
    "Selector de mapa base (ortofoto actual, ortofoto 2020, callejero y topográfico) y capas de referencia "
    "(término municipal, espacios protegidos y Red Natura 2000 de la REDIAM).",
    "Buscador de lugares por nombre, que activa la subcapa y centra el mapa en el resultado.",
    "Agrupación de puntos cercanos para que el mapa sea legible a cualquier escala.",
    "Ventana de información con atributos, aviso de ubicación aproximada y fuente del dato.",
    "Enlace permanente: la dirección de la página guarda las subcapas y el fondo activos, de modo que se puede "
    "compartir una vista concreta (por ejemplo, solo playas y chiringuitos).",
    "Diseño adaptado al móvil, con el panel de capas como hoja inferior desplegable.",
    "Actualización automática mensual de los datos abiertos.",
])
d.figura(cap("visor_movil_par.png"), "El prototipo en el móvil: mapa y panel de capas", fuente="AMMA Consulting",
         ancho_cm=11)
d.p(f"Dirección prevista de publicación: {URL}")
d.h2("Integración en el SITMA")
d.p("El prototipo no sustituye al SITMA: sirve para validar la estructura y entregar los datos ya preparados. "
    "Para la carga se propone:")
d.numerada([
    "Entregar los datos de cada subcapa en GeoJSON (o GeoPackage), en ETRS89 / UTM 30N (EPSG:25830), con el "
    "modelo de atributos de este documento.",
    "Publicarlos en el SITMA como servicios OGC (WMS para la visualización y WFS para la consulta), con el mismo "
    "árbol y los mismos nombres de capa y subcapa.",
    "Mantener el proceso automático de actualización de las fuentes abiertas y una tabla editable por la "
    "Delegación para los datos propios.",
    "Enlazar cada elemento con su ficha de la web de Turismo y, desde la web, abrir el visor ya centrado en el "
    "recurso.",
])

# =================================================================================================
d.h1("PRÓXIMOS PASOS")
numerada_nueva([
    "Validar con la Delegación de Turismo el árbol de capas y subcapas y la decisión sobre Turismo activo.",
    "Confirmar con el SITMA el formato de carga, el sistema de referencia y la disponibilidad de cartografía base.",
    "Revisar los datos del prototipo, en especial las subcapas marcadas como pendientes y las ubicaciones "
    "aproximadas.",
    "Marcar los «restaurantes destacados» y cargar los enlaces a las fichas de la web.",
    "Incorporar las traducciones de los textos en los idiomas de la web.",
    "Definir los responsables de cada subcapa y el calendario de revisión.",
])

d.guardar(SALIDA)
print(SALIDA)
