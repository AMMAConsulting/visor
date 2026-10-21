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
WEBR = json.load(open(os.path.join(RAIZ, "datos", "web_turismo.json"), encoding="utf8"))["recursos"]
G = {g["id"]: g for g in CAT["grupos"]}
S = {s["id"]: s for g in CAT["grupos"] for s in g["subcapas"]}
SALIDA = os.path.join(RAIZ, "Visor de Turismo SITMA - Estructura de capas y subcapas (formato AMMA).docx")
URL = "https://ammaconsulting.github.io/visor/"
N = lambda x: f"{x:,}".replace(",", ".")
total_sub = sum(len(g["subcapas"]) for g in CAT["grupos"])
sub_web = sum(1 for s in S.values() if not s["complementaria"])
total_el = sum(s["n"] for s in S.values())
total_sin = sum(s["sin_ubicacion"] for s in S.values())
rec_web = len({" ".join(r["titulo"].lower().split()) for r in WEBR})
ent_web = len(WEBR)

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


def fuente_corta(f):
    return (f.replace("OpenStreetMap (ODbL)", "OSM").replace("Registro de Turismo de Andalucía (OpenRTA)", "RTA")
             .replace("turismo.marbella.es", "Web").replace("; ", ", "))


# =================================================================================================
d.h1("INTRODUCCIÓN")
d.h2("Objeto del documento")
d.p("El Ayuntamiento de Marbella va a incorporar al SITMA, su Sistema de Información Territorial, una nueva "
    "capa de Turismo. Este documento describe la estructura completa de esa capa: el mapa base, las capas "
    "temáticas y sus subcapas, el contenido y la geometría de cada una, los atributos que debe tener cada "
    "elemento, las fuentes de datos que la alimentan y quién debe mantenerla.")
d.p("Acompaña al documento un prototipo web funcional, construido con datos reales, que permite ver la "
    "propuesta en funcionamiento antes de cargarla en el SITMA.")

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
d.p("Esta versión lleva esa premisa hasta el final: se ha leído el directorio completo de recursos de la web "
    "turismo.marbella.es y el visor lo reproduce sección por sección y categoría por categoría, con los mismos "
    "nombres y en el mismo orden. Las cinco capas de la propuesta inicial se mantienen en primer lugar; detrás "
    "van el resto de secciones de la web. Además, todos los recursos que la web promociona están representados "
    f"en el mapa: {N(rec_web)} recursos distintos ({N(ent_web)} entradas, porque un mismo recurso puede figurar "
    "en varias categorías).")

d.h2("Criterios de diseño")
d.vinetas([
    "Correspondencia exacta con la web de Turismo: cada sección de la web es una capa y cada categoría, una "
    "subcapa. Cada elemento del mapa lleva el nombre, la foto y el enlace a la ficha con que aparece en la web.",
    "Ningún recurso de la web sin representación. El proceso de carga comprueba que cada recurso publicado cae en "
    "una subcapa y genera un informe de cobertura; si la web estrena una categoría, sus recursos aparecen en una "
    "capa de control hasta que se les asigne subcapa.",
    "Información complementaria separada: lo que no está en la web pero es útil al visitante (otros restaurantes, "
    "miradores, carriles bici, farmacias…) va en «otras subcapas», al final de cada capa, sin mezclarse con las "
    "categorías de la web.",
    "Geometría definida: una playa, un parque o un campo de golf se dibujan con su superficie; un sendero, con su "
    "trazado; un restaurante, con un punto. La geometría se toma de OpenStreetMap o del Registro de Turismo de "
    "Andalucía cuando el recurso de la web se identifica en ellos.",
    "Sin duplicar el mantenimiento: la web es la fuente del directorio. Lo que la Delegación publica en la web "
    "llega al visor en la siguiente actualización, sin cargarlo dos veces.",
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
d.p(f"La capa de Turismo queda organizada en {len(CAT['grupos'])} capas y {total_sub} subcapas. De ellas, "
    f"{sub_web} reproducen una categoría de la web y {total_sub - sub_web} son complementarias. El prototipo "
    f"dibuja {N(total_el)} elementos; otros {total_sin} recursos de la web no tienen dirección física "
    "(guías, músicos, servicios en línea…) o la web no publica su ubicación, y se consultan en una lista dentro "
    "de su subcapa.")
SECCION = {"mar": "Vive · Mar", "golf": "Vive · Golf", "gastronomia": "Vive · Gastronomía",
           "alojamientos": "Vive · Alojamientos", "naturaleza": "Vive · Naturaleza", "compras": "Vive · Compras",
           "cultura": "Vive · Cultura", "deporte": "Vive · Deporte", "salud": "Vive · Salud y bienestar",
           "ocio": "Vive · Ocio", "mascotas": "Vive · Viajar con mascotas",
           "servicios": "Servicios · Oficinas, Servicios turísticos, Ruta fotográfica",
           "bodas": "Servicios · Marbella de boda", "profesional": "Área profesional · MICE, Empresas turísticas",
           "practica": "Descubre · Aparcamiento, Movilidad; Servicios · Contactos de interés",
           "control": "Categorías sin asignar"}
filas = [["Capa", "Sección de la web", "Subcapas (web + otras)", "Elementos"]]
for g in CAT["grupos"]:
    w = sum(1 for s in g["subcapas"] if not s["complementaria"])
    filas.append([g["titulo"], SECCION.get(g["id"], ""), f"{w} + {len(g['subcapas']) - w}" if len(g["subcapas"]) > w else str(w),
                  N(sum(s["n"] for s in g["subcapas"]))])
filas.append([[("Total", {"negrita": True})], "", [(f"{sub_web} + {total_sub - sub_web}", {"negrita": True})],
              [(N(total_el), {"negrita": True})]])
d.tabla(filas, anchos_cm=[3.6, 6.4, 3.0, 2.5], tam=10)
d.figura(cap("visor_todo.png"), "Prototipo del visor con subcapas de varias capas activas sobre la ortofoto",
         fuente="AMMA Consulting con datos de turismo.marbella.es, OSM, RTA, IGN y Guía MICHELIN/Repsol", ancho_cm=15)

d.h2("Cambios respecto a la propuesta inicial")
d.tabla([
    ["Cambio", "Motivo"],
    ["El árbol reproduce todo el directorio de la web: a las cinco capas iniciales se suman Compras, Cultura, "
     "Deporte, Salud y bienestar, Ocio, Viajar con mascotas, Servicios turísticos, Marbella de boda, Congresos y "
     "empresas e Información práctica",
     "Premisa de la propuesta: que visor y web sean homogéneos. Así ningún recurso que la web promociona queda "
     "fuera del mapa"],
    ["Cicloturismo y Turismo activo se mantienen dentro de Naturaleza",
     "Es donde los tiene la web. Si la web los separa, el visor lo hará en la siguiente actualización"],
    ["Dunas de Artola, Lago de las Tortugas y Senda del Litoral son subcapas, como en la web",
     "En la propuesta eran los únicos elementos sin subcapa"],
    ["Alojamientos se divide por categorías (hoteles de 1 a 5 estrellas y Gran Lujo, hoteles-apartamento, "
     "hostales, apartamentos turísticos de 1 a 4 llaves, pensiones, albergues y campings)",
     "Es la clasificación de la web; los datos de registro, plazas y coordenadas vienen del RTA"],
    ["Estrellas MICHELIN y Soles Repsol se mantienen como subcapas, pero se registran como atributo",
     "Un mismo restaurante puede tener ambas distinciones (BACK y Messina las tienen) y cambian cada año"],
    ["«Restaurantes destacados» es la selección de la web; el resto del censo va en «Otros restaurantes»",
     "Se respeta la selección de la Delegación y el visitante puede seguir encontrando cualquier restaurante"],
    ["«Otras subcapas» en cada capa: salvamento, otros restaurantes, alojamiento rural, Gran Senda de Málaga, "
     "miradores, carriles bici, patrimonio religioso, arte en la calle, cines, farmacias, aseos y recarga",
     "Información útil al visitante que la web no recoge; va aparte para no alterar las categorías de la web"],
    ["Ortofoto actual por defecto y selector de fondos con cartografía", "Responde a la cuestión abierta"],
], anchos_cm=[7.5, 8.0])

d.h2("Árbol completo")
d.p("La tabla recoge todas las subcapas en el orden en que aparecen en el visor. La columna «Web» indica si "
    "reproduce una categoría de la web o es complementaria; «Sin ubic.» cuenta los recursos de la web que no "
    "tienen ubicación y se consultan en la lista de la subcapa.")
filas = [["Capa", "Subcapa", "Geometría", "Elem.", "Sin ubic.", "Web"]]
for g in CAT["grupos"]:
    for i, s in enumerate(g["subcapas"]):
        filas.append([g["titulo"] if i == 0 else "", s["titulo"], s["geometria"].capitalize(), N(s["n"]),
                      str(s["sin_ubicacion"]) if s["sin_ubicacion"] else "",
                      "Complem." if s["complementaria"] else "Sí"])
d.tabla(filas, anchos_cm=[3.0, 5.6, 2.1, 1.5, 1.6, 1.7], tam=9.5)

# =================================================================================================
d.h1("DESCRIPCIÓN DE LAS CAPAS")
d.p("Para cada capa se describe su contenido, las subcapas con su geometría y su fuente, y las observaciones "
    "relevantes para cargarla en el SITMA. La columna «Nº» es la del prototipo a fecha de este documento; "
    "«Web» en la fuente indica turismo.marbella.es.")

NOTAS = {
    "mar": [
        "Playas: exactamente las 26 playas de la web, con su nombre, longitud y servicios (accesible, baño asistido, "
        "zona de moragas, admite mascotas) tal como figuran en su ficha. La arena se dibuja con los polígonos de "
        "OpenStreetMap, que agrupan varias playas en pocas áreas grandes: se reparten entre las playas de la web "
        "asignando a cada una la arena más próxima a su punto. Calahonda, sin arena cartografiada, va como punto.",
        "Distintivos de cada playa, que el visor muestra en su ficha: Bandera Azul 2026 según "
        "ADEAC (8 banderas de playa: Cabopino, El Cable, El Faro, La Fontanilla, Nagüeles-Casablanca, Los "
        "Monteros-Adelfas, Guadalmina y Venus-Bajadilla; y 2 de puerto: Puerto Banús y Virgen del Carmen), y Q de "
        "Calidad Turística y S de Sostenibilidad Turística según el registro oficial del ICTE (22 de las 26 playas "
        "tienen ambas; no las tienen El Ancón, El Pinillo, Cortijo Blanco y Ventura del Mar). Los datos y sus fuentes "
        "están en distintivos_playas.json y se revisan cada año.",
        "Dentro de Playas hay tres subcapas que se activan por separado: Con Q de Calidad Turística (22), Con S de "
        "Sostenibilidad Turística (22) y Accesibles: las cuatro playas con certificado de accesibilidad universal "
        "UNE 170001-2 (El Faro, La Bajadilla, Puerto Banús y San Pedro Alcántara, que en la web es La Salida). La web "
        "marca como accesible Nueva Andalucía en lugar de Puerto Banús.",
        "La web está desfasada en distintivos: muestra la Q en 15 playas (no recoge las certificadas en 2026: El "
        "Alicate, Calahonda, Las Cañas y Las Chapas, ni Cabopino, Puerto Banús o Linda Vista), no menciona la S, "
        "atribuye Bandera Azul a Nueva Andalucía y no a Cabopino. Conviene actualizar las fichas.",
        "Se recomienda añadir atributos de socorrismo, aseos y duchas, que la Delegación de Playas ya gestiona.",
        "Zonas de submarinismo (El Galeón, La Torre, Las Bóvedas, Pimpollo y Roqueillos) se dibujan en el punto que "
        "publica la web; Roqueillos no tiene ubicación en la web.",
        "Salvamento y socorrismo es complementaria: debe completarse con el plan de salvamento de cada temporada.",
    ],
    "golf": [
        "Cada campo tiene su propia página en la web; en el visor se agrupan en «Campos de golf» y se dibujan con su "
        "recinto, tomado de OpenStreetMap.",
    ],
    "gastronomia": [
        "Estrellas MICHELIN (edición 2026): Skina (2 Estrellas), BACK, Messina y Nintai (1 Estrella).",
        "Soles Repsol: la web cita Areia, El Lago, Kava, La Milla, Leña, Lobito de Mar, Messina y Ta-Kumi. La "
        "edición 2026 de la Guía añade BACK, que la web aún no recoge.",
        "Saboreando Marbella es la propuesta de producto local de la web (bodegas, conservas, ostras…).",
    ],
    "alojamientos": [
        "Cada categoría reúne los establecimientos que cita la web y los del Registro de Turismo de Andalucía de esa "
        "misma categoría que la web no cita, para que la oferta reglada esté completa. Del RTA vienen el número de "
        "registro, las plazas y las coordenadas.",
        "Las viviendas de uso turístico (más de 15.700 en Marbella según el RTA) se dejan fuera a propósito: no son "
        "un recurso que se promocione por unidad. Si se quieren mostrar, que sea como mapa de densidad en un "
        "apartado de análisis, no como puntos.",
    ],
    "naturaleza": [
        "Sierra Blanca se divide, como en la web, en cumbres y rutas de senderismo. Las rutas que tienen trazado en "
        "OpenStreetMap (PR-A 135, 140, 168, 169, 429 y 430 y la etapa Marbella–Ojén de la GR-249) se dibujan como "
        "línea; las demás, en su punto de inicio.",
        "Dunas de Artola es el Monumento Natural (Cabopino); la capa de referencia de la REDIAM añade la Red "
        "Natura 2000 de Sierra Blanca y el Parque Nacional Sierra de las Nieves, en el límite norte.",
    ],
    "cultura": [
        "Patrimonio histórico se divide, como en la web, en Casco histórico, Torres vigía, Arqueología y Patrimonio "
        "industrial. Se recomienda contrastarlo con la Guía Digital del Patrimonio Cultural de Andalucía (IAPH).",
        "Arte en la calle recoge las esculturas de Dalí de la Avenida del Mar y el resto de arte público.",
    ],
    "ocio": ["Ocio familiar incluye parques temáticos de la Costa del Sol (Selwo, Bioparc, Teleférico de "
             "Benalmádena…) que la web promociona aunque estén fuera del término; el visor lo indica en su ficha."],
    "servicios": ["Buena parte de los guías turísticos y de las experiencias no tienen dirección física: figuran en "
                  "la lista «sin ubicación en el mapa» de su subcapa, con el enlace a su ficha."],
    "profesional": ["Empresas turísticas incluye asociaciones y turoperadores con sede fuera de Marbella "
                    "(Torremolinos, Málaga, Madrid), que se ubican en su dirección."],
    "practica": [
        "Aparcamientos reúne los de la web (públicos, de centros comerciales y de playa) y los aparcamientos "
        "públicos de OpenStreetMap.",
        "Puntos de recarga puede completarse con el Punto de Acceso Nacional de datos de recarga.",
    ],
}

for g in CAT["grupos"]:
    d.h2(g["titulo"])
    d.p(g["descripcion"] + (f" Corresponde a {SECCION[g['id']]} de la web." if g["id"] in SECCION else ""))
    filas = [["Subcapa", "Contenido", "Geom.", "Fuente", "Nº"]]
    for s in g["subcapas"]:
        filas.append([[(s["titulo"], {"negrita": True})] + ([(" (otra subcapa)", {"cursiva": True})]
                                                              if s["complementaria"] else []),
                      s["descripcion"].replace(" (complementaria)", ""), s["geometria"].capitalize(),
                      fuente_corta(s["fuente"]), N(s["n"]) + (f" + {s['sin_ubicacion']}" if s["sin_ubicacion"] else "")])
    d.tabla(filas, anchos_cm=[3.4, 6.0, 1.8, 3.0, 1.3], tam=9.5)
    if g["id"] in NOTAS:
        d.vinetas(NOTAS[g["id"]])
    if g["id"] == "naturaleza":
        d.figura(cap("visor_naturaleza.png"), "Capa Naturaleza sobre el mapa topográfico: Dunas de Artola, Lago de "
                 "las Tortugas, Senda del Litoral, cicloturismo, turismo activo y Sierra Blanca",
                 fuente="AMMA Consulting con datos de turismo.marbella.es, OSM e IGN", ancho_cm=15)
    if g["id"] == "mar":
        d.figura(cap("visor_playa.png"), "Playas, chiringuitos, clubs de playa y zonas de submarinismo en La Fontanilla",
                 fuente="AMMA Consulting con datos de turismo.marbella.es, OSM e IGN", ancho_cm=15)
d.p("En la columna «Nº», la cifra tras el signo «+» son los recursos sin ubicación en el mapa.")

# =================================================================================================
d.h1("MODELO DE DATOS")
d.h2("Atributos comunes")
d.p("Todas las subcapas comparten un mismo conjunto de atributos, de modo que la ventana de información del "
    "visor es igual en todas y los datos se pueden reutilizar en la web, la app o el Observatorio Turístico.")
d.tabla([
    ["Campo", "Descripción", "Oblig."],
    ["id", "Identificador único y estable del elemento (el de la ficha de la web cuando la hay)", "Sí"],
    ["capa / subcapa", "Código de la capa y de la subcapa (p. ej. mar / playas)", "Sí"],
    ["nombre", "Nombre con que aparece en la web", "Sí"],
    ["categoria", "Categoría (estrellas, llaves, tipo de servicio…)", "Recom."],
    ["descripcion_es / _en", "Texto breve en español e inglés (y demás idiomas de la web)", "Recom."],
    ["direccion", "Dirección postal normalizada (callejero municipal)", "Sí"],
    ["telefono, web, email", "Datos de contacto", "Recom."],
    ["url_ficha", "Enlace a la ficha del recurso en la web de Turismo", "Sí"],
    ["foto", "Imagen principal (la de la ficha de la web)", "Recom."],
    ["horario", "Horario de apertura (formato normalizado)", "Opcional"],
    ["accesibilidad", "Accesible para personas con movilidad reducida (sí / no / parcial)", "Recom."],
    ["fuente", "Origen del dato (web de Turismo, RTA, OSM…)", "Sí"],
    ["aviso", "Ubicación aproximada, fuera del término o sin ubicación", "Si procede"],
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
    ["Senderos y rutas", "Código (GR, PR-A, SL-A), longitud, desnivel, dificultad, duración, archivo GPX"],
    ["Patrimonio", "Época, protección (BIC, catalogado), horario de visita, precio"],
], anchos_cm=[4.0, 11.5])
d.h2("Ventana de información")
d.p("Al pulsar un elemento se abre una ventana con la foto de la ficha de la web, la capa y la subcapa, el nombre, "
    "los atributos disponibles, el enlace «Ver ficha» a la web de Turismo y la fuente del dato. Si la ubicación es "
    "aproximada (por ejemplo, porque se ha obtenido a partir de la dirección) o el recurso está fuera del término, "
    "se avisa.")
d.figura(cap("visor_popup.png"), "Ventana de información de un recurso de «Saboreando Marbella», con la foto y el "
         "enlace a su ficha", fuente="AMMA Consulting con datos de turismo.marbella.es e IGN", ancho_cm=14)
d.h2("Recursos sin ubicación")
d.p(f"{total_sin} recursos de la web no se pueden situar en el mapa: personas (guías, músicos, oficiantes, "
    "traductores), servicios en línea y empresas cuya ficha no da coordenadas ni una dirección localizable. Para "
    "que ninguno se quede fuera, cada subcapa que los tiene muestra bajo su nombre un enlace «sin ubicación en el "
    "mapa» que abre la lista, con la dirección (si la hay) y el enlace a la ficha. Cuando la web publique sus "
    "coordenadas pasarán al mapa automáticamente.")
d.figura(cap("visor_lista.png"), "Lista de guías turísticos sin ubicación en el mapa",
         fuente="AMMA Consulting con datos de turismo.marbella.es", ancho_cm=14)
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
    ["Web de Turismo (turismo.marbella.es)", "Ayuntamiento de Marbella", "Directorio de recursos: categorías, nombres, "
     "coordenadas, direcciones, fotos y fichas", "Lectura automática de la web", "Mensual"],
    ["Registro de Turismo de Andalucía (OpenRTA)", "Junta de Andalucía", "Alojamientos, turismo activo, oficinas de "
     "turismo", "API JSON abierta", "Mensual"],
    ["OpenStreetMap", "Comunidad OSM (ODbL)", "Geometría de playas, puertos, golf, parques y rutas; recursos "
     "complementarios", "Extracto Geofabrik", "Mensual"],
    ["PNOA, IGN Base, MTN", "Instituto Geográfico Nacional", "Ortofotos y cartografía base", "WMS / WMTS", "Periódica"],
    ["Espacios protegidos y Red Natura", "REDIAM (Junta de Andalucía)", "Límites oficiales", "WMS", "Periódica"],
    ["CartoCiudad", "IGN", "Geocodificación de direcciones", "API abierta", "Continua"],
    ["Guía MICHELIN", "Michelin", "Estrellas", "Web pública", "Anual (noviembre)"],
    ["Guía Repsol", "Repsol", "Soles", "Web pública", "Anual (febrero)"],
    ["Bandera Azul", "ADEAC", "Playas y puertos galardonados", "Web pública", "Anual (mayo)"],
], anchos_cm=[3.6, 2.9, 4.0, 2.6, 2.4], tam=10)
d.h2("Responsables y periodicidad")
d.tabla([
    ["Capas o subcapas", "Responsable propuesto", "Revisión"],
    ["Directorio de recursos (todas las categorías de la web)", "Delegación de Turismo, al publicar en la web; el "
     "visor se actualiza solo", "Mensual"],
    ["Alojamientos (RTA) y datos de OpenStreetMap", "Automática (proceso mensual)", "Mensual"],
    ["Coordenadas de los recursos sin ubicación", "Delegación de Turismo (en la ficha de la web)", "Continua"],
    ["Distinciones gastronómicas y Bandera Azul", "Delegación de Turismo", "Anual, tras cada edición"],
    ["Playas, salvamento y servicios de playa", "Delegación de Playas", "Cada temporada"],
    ["Parques, espacios naturales y senderos", "Medio Ambiente / Parques y Jardines", "Anual"],
    ["Mapa base, término y publicación", "SITMA", "Según el servicio"],
], anchos_cm=[6.5, 5.5, 3.5])
d.h2("Control de cobertura")
d.p("Cada actualización genera un informe (cobertura_web.md) con cada página de la web, el número de recursos que "
    "publica, la subcapa del visor que los recoge y cuántos no tienen ubicación. A fecha de este documento, "
    f"{N(ent_web)} entradas de la web están asignadas a una subcapa y ninguna queda fuera.")
pend = [s for s in S.values() if s["pendiente"]]
if pend:
    d.h2("Datos pendientes de alta")
    d.p("Estas subcapas complementarias no tienen hoy una fuente abierta completa:")
    d.vinetas([[(s["titulo"] + ": ", {"negrita": True}), (s["pendiente"][0].lower() + s["pendiente"][1:] + ".", {})]
               for s in pend])

# =================================================================================================
d.h1("PROTOTIPO WEB")
d.h2("Descripción")
d.p("Para validar la estructura se ha construido un prototipo web que ya funciona con datos reales. Reproduce el "
    "comportamiento esperado del visor en el SITMA:")
d.vinetas([
    "Árbol de capas y subcapas en el orden de la web de Turismo, con casilla por subcapa y por capa completa, "
    "el número de elementos de cada una y, separadas, las «otras subcapas».",
    "Selector de mapa base (ortofoto actual, ortofoto 2020, callejero y topográfico) y capas de referencia "
    "(término municipal, espacios protegidos y Red Natura 2000 de la REDIAM).",
    "Buscador de lugares por nombre, que activa la subcapa y centra el mapa en el resultado.",
    "Agrupación de puntos cercanos para que el mapa sea legible a cualquier escala.",
    "Ventana de información con foto, atributos, enlace a la ficha de la web, avisos y fuente del dato.",
    "Lista de recursos sin ubicación en cada subcapa que los tiene.",
    "Enlace permanente: la dirección de la página guarda las subcapas y el fondo activos, de modo que se puede "
    "compartir una vista concreta (por ejemplo, solo playas y chiringuitos).",
    "Diseño adaptado al móvil, con el panel de capas como hoja inferior desplegable.",
    "Actualización automática mensual a partir de la web de Turismo y de las fuentes abiertas.",
])
d.figura(cap("visor_movil_par.png"), "El prototipo en el móvil: mapa y panel de capas", fuente="AMMA Consulting",
         ancho_cm=11)
d.p(f"Dirección del prototipo: {URL}")
d.h2("Integración en el SITMA")
d.p("El prototipo no sustituye al SITMA: sirve para validar la estructura y entregar los datos ya preparados. "
    "Para la carga se propone:")
d.numerada([
    "Entregar los datos de cada subcapa en GeoJSON (o GeoPackage), en ETRS89 / UTM 30N (EPSG:25830), con el "
    "modelo de atributos de este documento.",
    "Publicarlos en el SITMA como servicios OGC (WMS para la visualización y WFS para la consulta), con el mismo "
    "árbol y los mismos nombres de capa y subcapa.",
    "Mantener el proceso automático de actualización desde la web de Turismo y las fuentes abiertas.",
    "Desde la web, abrir el visor ya centrado en el recurso, con un enlace en cada ficha.",
])

# =================================================================================================
d.h1("PRÓXIMOS PASOS")
numerada_nueva([
    "Validar con la Delegación de Turismo el árbol de capas y subcapas y las «otras subcapas» complementarias.",
    "Confirmar con el SITMA el formato de carga, el sistema de referencia y la disponibilidad de cartografía base.",
    f"Completar en la web las coordenadas de los {total_sin} recursos sin ubicación que tengan sede física y "
    "revisar las ubicaciones aproximadas.",
    "Revisar las fichas de la web con datos incompletos (sin dirección o con la categoría en el campo de "
    "dirección), que se arrastran al visor.",
    "Incorporar las traducciones de los textos en los idiomas de la web.",
    "Definir los responsables de cada subcapa y el calendario de revisión.",
])

# =================================================================================================
d.h1("ANEXO. CORRESPONDENCIA CON LA WEB DE TURISMO")
d.p("Cada página de categoría de turismo.marbella.es, la subcapa del visor que la reproduce y el número de "
    "entradas que publica.")
PAGINAS = {w.replace("https://turismo.marbella.es", "")[:-5] for s in S.values() for w in (s["web"] or [])}


def pagina_de(p):
    """Página de categoría más próxima a la que pertenece una entrada de la web."""
    partes = p[:-5].split("/")
    return next(("/".join(partes[:i]) for i in range(len(partes), 1, -1) if "/".join(partes[:i]) in PAGINAS), None)


cuenta = {}
for r in WEBR:
    cuenta[pagina_de(r["pagina"])] = cuenta.get(pagina_de(r["pagina"]), 0) + 1
filas = [["Página de la web", "Subcapa del visor", "Entradas"]]
for g in CAT["grupos"]:
    for s in g["subcapas"]:
        for w in s["web"] or []:
            ruta = w.replace("https://turismo.marbella.es", "")[:-5]
            filas.append([ruta, f"{g['titulo']} · {s['titulo']}", str(cuenta.get(ruta, 0))])
d.tabla(filas, anchos_cm=[8.2, 6.0, 1.6], tam=8.5)

d.guardar(SALIDA)
print(SALIDA)
