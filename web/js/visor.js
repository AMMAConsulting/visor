/* Visor (AMMA Consulting)
   Lee data/catalogo.json (capas → subcapas) y un GeoJSON por subcapa. */

const ICONOS = {
  // capas
  mar: "waves", golf: "golf_course", gastronomia: "restaurant", alojamientos: "hotel", naturaleza: "forest",
  compras: "local_mall", cultura: "account_balance", deporte: "sports_tennis", salud: "spa", ocio: "nightlife",
  mascotas: "pets", servicios: "tour", bodas: "favorite", profesional: "business_center", practica: "info",
  control: "help",
  // subcapas
  actividades_nauticas: "sailing", playas: "beach_access", puertos: "anchor", clubes_playa: "deck", buceo: "scuba_diving",
  salvamento: "support",
  campos_golf: "golf_course", academias_golf: "sports_golf", tiendas_golf: "storefront", alquiler_golf: "shopping_cart",
  michelin: "star", repsol: "wb_sunny", saboreando: "tapas", restaurantes: "restaurant", chiringuitos: "kebab_dining",
  catering: "room_service", vinotecas: "wine_bar", delicatessen: "bakery_dining", otros_restaurantes: "restaurant_menu",
  hoteles_5gl: "hotel", hoteles_5: "hotel", hoteles_4: "hotel", hoteles_3: "hotel", hoteles_2: "hotel", hoteles_1: "hotel",
  hoteles_apto_4: "apartment", hoteles_apto_3: "apartment", hostales_2: "bed", hostales_1: "bed",
  at_4: "domain", at_3: "domain", at_2: "domain", at_1: "domain", pensiones: "single_bed", albergues: "night_shelter",
  campings: "camping", aloj_otros: "hotel_class", rural: "cottage",
  dunas_artola: "landscape_2", lago_tortugas: "water", senda_litoral: "hiking", cicloturismo: "pedal_bike",
  turismo_activo: "kayaking", cumbres: "landscape", senderos: "hiking", parques: "park", gr249: "hiking",
  miradores: "visibility", carriles_bici: "pedal_bike", rutas_ciclistas: "directions_bike",
  mercadillos: "shopping_basket", centros_comerciales: "local_mall", firmas_moda: "checkroom",
  centros_culturales: "theater_comedy", galerias: "palette", casco_historico: "castle", torres_vigia: "fort",
  arqueologia: "temple_buddhist", patrimonio_industrial: "factory", patrimonio_religioso: "church",
  monumentos: "account_balance", arte_urbano: "brush",
  equitacion: "bedroom_baby", gimnasios: "fitness_center", tenis_padel: "sports_tennis", yoga: "self_improvement",
  spa: "spa", estetica: "face_retouching_natural", salud: "local_hospital",
  flamenco: "music_note", ocio_familiar: "attractions", ocio_nocturno: "nightlife", rooftops: "roofing", cines: "movie",
  veterinarios: "medical_services", servicios_mascotas: "content_cut", hoteles_mascotas: "house", parques_caninos: "park",
  admiten_mascotas: "pets",
  oficinas_turismo: "info", agencias: "luggage", alquiler_coches: "directions_car", guias: "tour",
  alquiler_autobuses: "directions_bus", alquiler_barcos: "directions_boat", transfer: "airport_shuttle",
  alquiler_aereo: "flight", caravanas: "rv_hookup", experiencias: "explore", cambio: "currency_exchange",
  consigna: "luggage", ruta_fotografica: "photo_camera",
  bodas_lugares: "celebration", bodas_ceremonias: "church", bodas_organizadores: "event", bodas_oficiantes: "record_voice_over",
  bodas_complementarios: "local_florist", bodas_alquiler: "chair",
  mice_recintos: "stadium", mice_negocios: "business_center", mice_traductores: "translate", mice_azafatas: "badge",
  mice_dmc: "event_available", empresas_turisticas: "groups",
  aparcamientos: "local_parking", movilidad: "directions_bus", emergencias: "emergency", contactos_otros: "call",
  farmacias: "local_pharmacy", aseos: "wc", recarga: "ev_station", otros_web: "help",
};

const ETIQUETAS = {
  categoria: "Categoría", direccion: "Dirección", telefono: "Teléfono", web: "Web", horario: "Horario",
  cocina: "Cocina", bandera_azul: "Bandera Azul", registro: "Nº de registro", plazas: "Plazas", unidades: "Unidades",
  otras_distinciones: "Otras distinciones", altitud: "Altitud", otros_nombres: "Otros nombres", ref: "Código",
  etapa: "Etapa", tipo: "Tipo", autor: "Autor", accesible: "Accesible", longitud: "Longitud",
  q_calidad: "Q de Calidad", s_sostenibilidad: "S de Sostenibilidad", servicios: "Servicios",
  admite_mascotas: "Admite mascotas",
};
const PIN_EN_AREAS = new Set(["playas", "puertos", "campos_golf", "lago_tortugas", "campings", "dunas_artola", "parques",
  "admiten_mascotas", "parques_caninos"]);
const OCULTAS = new Set(["nombre", "fuente", "aviso", "origen", "imagen", "ficha", "sellos", "pin"]);
// distintivos de playas y puertos: Bandera Azul (ADEAC), Q de Calidad y S de Sostenibilidad Turística (ICTE)
const SELLOS = {
  AZ: { corto: '<span class="ms">flag</span>', largo: "Bandera Azul", clase: "az" },
  Q: { corto: "Q", largo: "Q de Calidad Turística", clase: "q" },
  S: { corto: "S", largo: "S de Sostenibilidad Turística", clase: "s" },
};
const sellosDe = (p) => (p.sellos ? p.sellos.split(",") : []).filter((x) => SELLOS[x]);
const TIPOS_HIST = { castle: "Castillo", fort: "Fuerte", tower: "Torre", city_gate: "Puerta de la ciudad", ruins: "Ruinas",
  building: "Edificio histórico", monument: "Monumento", manor: "Casa señorial", watermill: "Molino", mine: "Mina",
  house: "Casa histórica", church: "Iglesia", monastery: "Convento", wayside_cross: "Cruz", underground: "Subterráneo",
  "multi-storey": "En altura", surface: "En superficie" };

const FONDOS = [
  { id: "orto", nombre: "Ortofoto actual", capa: () => L.layerGroup([
      L.tileLayer(wmts("https://www.ign.es/wmts/pnoa-ma", "OI.OrthoimageCoverage", "image/jpeg"), { maxZoom: 20, maxNativeZoom: 19, attribution: "PNOA © IGN" }),
      L.tileLayer(wmts("https://www.ign.es/wmts/ign-base", "IGNBaseOrto", "image/png"), { maxZoom: 20, maxNativeZoom: 18 })]) },
  { id: "orto2020", nombre: "Ortofoto 2020", capa: () => L.tileLayer.wms("https://www.ign.es/wms/pnoa-historico",
      { layers: "PNOA2020", format: "image/jpeg", maxZoom: 20, attribution: "PNOA 2020 © IGN" }) },
  { id: "callejero", nombre: "Callejero", capa: () => L.tileLayer(wmts("https://www.ign.es/wmts/ign-base", "IGNBaseTodo", "image/png"),
      { maxZoom: 20, maxNativeZoom: 18, attribution: "IGN Base © IGN" }) },
  { id: "topo", nombre: "Topográfico", capa: () => L.tileLayer(wmts("https://www.ign.es/wmts/mapa-raster", "MTN", "image/jpeg"),
      { maxZoom: 20, maxNativeZoom: 17, attribution: "MTN © IGN" }) },
];
const SUPERPUESTAS = [
  { id: "enp", nombre: "Espacios protegidos (REDIAM)", capa: () => L.tileLayer.wms(
      "https://www.juntadeandalucia.es/medioambiente/mapwms/REDIAM_RENPA", { layers: "eennpp", format: "image/png",
      transparent: true, opacity: .6, attribution: "REDIAM, Junta de Andalucía" }) },
  { id: "natura", nombre: "Red Natura 2000 (REDIAM)", capa: () => L.tileLayer.wms(
      "https://www.juntadeandalucia.es/medioambiente/mapwms/REDIAM_RENPA", { layers: "red_natura_2000", format: "image/png",
      transparent: true, opacity: .55, attribution: "REDIAM, Junta de Andalucía" }) },
  { id: "termino", nombre: "Término municipal", capa: () => terminoCapa },
];

function wmts(url, capa, formato) {
  return `${url}?service=WMTS&request=GetTile&version=1.0.0&layer=${capa}&style=default&format=${formato}` +
         `&tilematrixset=GoogleMapsCompatible&tilematrix={z}&tilerow={y}&tilecol={x}`;
}

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

const mapa = L.map("mapa", { zoomControl: false, minZoom: 10, maxZoom: 20 }).setView([36.505, -4.89], 13);
L.control.zoom({ position: "topright" }).addTo(mapa);
L.control.scale({ imperial: false, position: "bottomright" }).addTo(mapa);

const cluster = L.markerClusterGroup({
  disableClusteringAtZoom: 17, maxClusterRadius: 42, showCoverageOnHover: false, spiderfyOnMaxZoom: true,
  iconCreateFunction: (c) => L.divIcon({ html: `<div class="marker-cluster-custom" style="width:36px;height:36px">${c.getChildCount()}</div>`,
                                          className: "", iconSize: [36, 36] }),
});
mapa.addLayer(cluster);
const capasLineales = L.layerGroup().addTo(mapa);

let catalogo, terminoCapa, fondoActual;
const subcapas = {};       // id → {meta, grupo, capa (L.GeoJSON), marcadores[], activa}
const indice = [];         // para el buscador

// ---------------------------------------------------------------------------------------------
function iconoPin(sc, f) {
  const dist = sc.meta.id === "michelin" || sc.meta.id === "repsol";
  return L.divIcon({
    className: "", iconSize: [28, 28], iconAnchor: [14, 14], popupAnchor: [0, -12],
    html: `<div class="pin${dist ? " dist" : ""}" style="background:${sc.meta.color}"><span class="ms">${ICONOS[sc.meta.id] || "place"}</span>` +
      (sellosDe(f.properties).length ? `<span class="sellos">${sellosDe(f.properties).map((x) =>
        `<i class="${SELLOS[x].clase}">${SELLOS[x].corto}</i>`).join("")}</span>` : "") + `</div>`,
  });
}

function valor(k, v) {
  if (k === "web") {
    const url = /^https?:/i.test(v) ? v : "https://" + v;
    return `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(v.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, ""))}</a>`;
  }
  if (k === "telefono") return `<a href="tel:${esc(v.replace(/\s/g, ""))}">${esc(v)}</a>`;
  if (k === "tipo") return esc(TIPOS_HIST[v] || v);
  return esc(v);
}

function popup(sc, f) {
  const p = f.properties;
  const filas = Object.entries(p).filter(([k, v]) => !OCULTAS.has(k) && v !== "" && v != null && ETIQUETAS[k])
    .map(([k, v]) => `<tr><th>${ETIQUETAS[k]}</th><td>${valor(k, String(v))}</td></tr>`).join("");
  const enlaceFuente = p.origen ? ` · <a href="${esc(p.origen)}" target="_blank" rel="noopener">ver en OpenStreetMap</a>` : "";
  return `<div class="pop">
    ${p.imagen ? `<img class="foto" src="${esc(p.imagen)}" alt="" loading="lazy" onerror="this.remove()">` : ""}
    <div class="capa" style="color:${sc.meta.color}">${esc(sc.grupo.titulo)} · ${esc(sc.meta.titulo)}</div>
    <h3>${esc(p.nombre || sc.meta.titulo)}</h3>
    ${sellosDe(p).length ? `<div class="chips">${sellosDe(p).map((x) =>
      `<span class="chip-sello ${SELLOS[x].clase}">${x === "AZ" ? SELLOS[x].corto + " " : ""}${SELLOS[x].largo}</span>`).join("")}</div>` : ""}
    ${filas ? `<table>${filas}</table>` : ""}
    ${p.aviso ? `<div class="aviso">${esc(p.aviso)}</div>` : ""}
    ${p.ficha ? `<a class="ver-ficha" href="${esc(p.ficha)}" target="_blank" rel="noopener">Ver ficha <span class="ms">open_in_new</span></a>` : ""}
    <div class="fuente">Fuente: ${esc(p.fuente || sc.meta.fuente)}${enlaceFuente}</div>
  </div>`;
}

function construirCapa(sc, gj) {
  sc.sinUbicacion = gj.features.filter((f) => !f.geometry);
  const capa = L.geoJSON({ type: "FeatureCollection", features: gj.features.filter((f) => f.geometry) }, {
    style: (f) => /Line/.test(f.geometry.type)
      ? { color: sc.meta.color, weight: sc.meta.id === "carriles_bici" ? 3 : 4, opacity: .95, dashArray: sc.meta.id === "senderos" ? "6 5" : null }
      : { color: sc.meta.color, weight: 2, fillColor: sc.meta.color, fillOpacity: sc.meta.id === "dunas_artola" ? .2 : .32 },
    pointToLayer: (f, ll) => L.marker(ll, { icon: iconoPin(sc, f), title: f.properties.nombre || "" }),
    onEachFeature: (f, l) => {
      l.bindPopup(() => popup(sc, f), { maxWidth: 320 });
      const ll = l.getLatLng ? l.getLatLng() : l.getBounds().getCenter();
      indice.push({ nombre: f.properties.nombre || sc.meta.titulo, sc, capa: l, ll, n: norm(f.properties.nombre) });
    },
  });
  sc.capa = capa;
  // los puntos van al agrupador; las líneas y las áreas, a su propia capa
  sc.marcadores = capa.getLayers().filter((l) => l.getLatLng);
  sc.formas = L.featureGroup(capa.getLayers().filter((l) => !l.getLatLng));
  // las áreas pequeñas o alargadas (playas, puertos, campos de golf…) llevan además un marcador clicable
  if (PIN_EN_AREAS.has(sc.meta.id)) {
    sc.formas.eachLayer((l) => {
      if (/Line/.test(l.feature.geometry.type)) return;
      const pin = l.feature.properties.pin;
      const m = L.marker(pin ? [pin[1], pin[0]] : l.getBounds().getCenter(), { icon: iconoPin(sc, l.feature), title: l.feature.properties.nombre || "" });
      m.bindPopup(() => popup(sc, l.feature), { maxWidth: 320 });
      sc.marcadores.push(m);
    });
  }
}

function activar(id, on, sinHash) {
  const sc = subcapas[id];
  if (!sc || !sc.capa || !sc.meta.n || sc.activa === on) return;
  sc.activa = on;
  if (sc.marcadores.length) on ? cluster.addLayers(sc.marcadores) : cluster.removeLayers(sc.marcadores);
  if (sc.formas.getLayers().length) on ? capasLineales.addLayer(sc.formas) : capasLineales.removeLayer(sc.formas);
  const cb = document.getElementById("cb-" + id);
  if (cb) cb.checked = on;
  actualizarGrupo(sc.grupo.id);
  if (!sinHash) guardarHash();
}

function actualizarGrupo(gid) {
  const g = catalogo.grupos.find((x) => x.id === gid);
  const cbs = g.subcapas.filter((s) => s.n > 0).map((s) => subcapas[s.id].activa);
  const cb = document.getElementById("cbg-" + gid);
  cb.checked = cbs.length && cbs.every(Boolean);
  cb.indeterminate = cbs.some(Boolean) && !cb.checked;
  const n = g.subcapas.filter((s) => subcapas[s.id].activa).length;
  document.getElementById("cnt-" + gid).textContent = n ? `${n}/${g.subcapas.length}` : `${g.subcapas.length}`;
  const total = Object.values(subcapas).filter((s) => s.activa).length;
  $("#resumen").textContent = total ? `${total} subcapa${total > 1 ? "s" : ""} visible${total > 1 ? "s" : ""}` : "Ninguna subcapa visible";
}

// ---------------------------------------------------------------------------------------------
function pintarArbol() {
  const arbol = $("#arbol");
  arbol.innerHTML = catalogo.grupos.map((g) => `
    <div class="grupo" id="g-${g.id}">
      <div class="cab" data-g="${g.id}">
        <input type="checkbox" id="cbg-${g.id}" aria-label="Activar todo ${esc(g.titulo)}">
        <span class="chip" style="background:${g.color}"><span class="ms">${ICONOS[g.id]}</span></span>
        <span class="tit">${esc(g.titulo)}</span>
        <span class="cnt" id="cnt-${g.id}">${g.subcapas.length}</span>
        <span class="ms flecha">chevron_right</span>
      </div>
      <ul>${g.subcapas.map((s, i) => `
        ${i && s.complementaria && !g.subcapas[i - 1].complementaria ? '<li class="sep">Otras subcapas</li>' : ""}
        <li><label class="sub-capa" title="${esc(s.descripcion)}">
          <input type="checkbox" id="cb-${s.id}" ${s.n ? "" : "disabled"}>
          <span class="sim ${s.geometria === "línea" ? "linea" : s.geometria === "polígono" ? "poli" : ""}" style="background:${s.color}">
            ${s.geometria === "línea" ? "" : `<span class="ms">${ICONOS[s.id] || "place"}</span>`}</span>
          <span class="nom">${esc(s.titulo)}</span>
          ${s.pendiente && !s.n ? '<span class="etq-pend" title="' + esc(s.pendiente) + '">pendiente</span>' : `<span class="n">${s.n}</span>`}
        </label>${s.sin_ubicacion ? `<button class="sin-ub" data-s="${s.id}">+ ${s.sin_ubicacion} sin ubicación en el mapa</button>` : ""}</li>`).join("")}
      </ul>
    </div>`).join("");

  arbol.addEventListener("click", (ev) => {
    const cab = ev.target.closest(".cab");
    if (!cab) return;
    const gid = cab.dataset.g;
    if (ev.target.matches("input")) {
      const on = ev.target.checked;
      catalogo.grupos.find((g) => g.id === gid).subcapas.forEach((s) => s.n && activar(s.id, on, true));
      guardarHash();
      $("#g-" + gid).classList.add("abierto");
      return;
    }
    $("#g-" + gid).classList.toggle("abierto");
  });
  arbol.addEventListener("click", (ev) => {
    const b = ev.target.closest(".sin-ub");
    if (b) listaSinUbicacion(subcapas[b.dataset.s]);
  });
  arbol.addEventListener("change", (ev) => {
    if (ev.target.id.startsWith("cb-")) activar(ev.target.id.slice(3), ev.target.checked);
  });
}

function listaSinUbicacion(sc) {
  $("#tituloLista").textContent = `${sc.grupo.titulo} · ${sc.meta.titulo}`;
  $("#cuerpoLista").innerHTML = (sc.sinUbicacion || []).map((f) => {
    const p = f.properties;
    return `<li><strong>${esc(p.nombre)}</strong>${p.categoria ? ` <small>${esc(p.categoria)}</small>` : ""}
      ${p.direccion ? `<div>${esc(p.direccion)}</div>` : ""}
      ${p.ficha ? `<a href="${esc(p.ficha)}" target="_blank" rel="noopener">Ver ficha</a>` : ""}</li>`;
  }).join("");
  $("#dlgLista").showModal();
}

function pintarFondos() {
  $("#fondos").innerHTML = FONDOS.map((f) =>
    `<label><input type="radio" name="fondo" value="${f.id}">${esc(f.nombre)}</label>`).join("");
  $("#superpuestas").innerHTML = SUPERPUESTAS.map((f) =>
    `<label><input type="checkbox" value="${f.id}">${esc(f.nombre)}</label>`).join("");
  $("#fondos").addEventListener("change", (e) => { ponerFondo(e.target.value); guardarHash(); });
  $("#superpuestas").addEventListener("change", (e) => {
    const s = SUPERPUESTAS.find((x) => x.id === e.target.value);
    s._capa = s._capa || s.capa();
    e.target.checked ? s._capa.addTo(mapa) : mapa.removeLayer(s._capa);
    if (e.target.checked && s.id !== "termino") s._capa.bringToFront?.();
    guardarHash();
  });
}

function ponerFondo(id) {
  const f = FONDOS.find((x) => x.id === id) || FONDOS[0];
  if (fondoActual) mapa.removeLayer(fondoActual._capa);
  f._capa = f._capa || f.capa();
  f._capa.addTo(mapa);
  f._capa.eachLayer ? f._capa.eachLayer((l) => l.bringToBack()) : f._capa.bringToBack();
  fondoActual = f;
  document.querySelector(`#fondos input[value="${f.id}"]`).checked = true;
  $("#fondoActual").textContent = f.nombre;
}

// ---------------------------------------------------------------------------------------------
function buscador() {
  const inp = $("#buscar"), ul = $("#resultados");
  let sel = -1, actuales = [];
  const pintar = () => {
    const q = norm(inp.value.trim());
    if (q.length < 2) { ul.hidden = true; return; }
    const pal = (x) => (x.n.startsWith(q) || x.n.includes(" " + q)) ? 0 : 1;   // coincide al inicio de una palabra
    actuales = indice.filter((x) => x.n.includes(q))
      .sort((a, b) => pal(a) - pal(b) || a.sc.meta.n - b.sc.meta.n || a.n.length - b.n.length).slice(0, 12);
    sel = -1;
    ul.innerHTML = actuales.length ? actuales.map((x, i) => `<li data-i="${i}"><span class="punto" style="background:${x.sc.meta.color}"></span>
      ${esc(x.nombre)}<small>${esc(x.sc.meta.titulo)}</small></li>`).join("") : `<li>Sin resultados</li>`;
    ul.hidden = false;
  };
  const ir = (x) => {
    if (!x) return;
    activar(x.sc.meta.id, true);
    ul.hidden = true; inp.value = x.nombre;
    if (x.capa.getLatLng) {
      cluster.zoomToShowLayer(x.capa, () => x.capa.openPopup());
    } else {
      mapa.fitBounds(x.capa.getBounds(), { maxZoom: 17, padding: [40, 40] });
      x.capa.openPopup(x.ll);
    }
    if (innerWidth <= 720) document.body.classList.add("sin-panel");
  };
  inp.addEventListener("input", pintar);
  inp.addEventListener("keydown", (e) => {
    const lis = [...ul.querySelectorAll("li[data-i]")];
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      sel = Math.max(0, Math.min(lis.length - 1, sel + (e.key === "ArrowDown" ? 1 : -1)));
      lis.forEach((li, i) => li.classList.toggle("activo", i === sel));
    } else if (e.key === "Enter") ir(actuales[Math.max(sel, 0)]);
    else if (e.key === "Escape") ul.hidden = true;
  });
  ul.addEventListener("click", (e) => { const li = e.target.closest("li[data-i]"); if (li) ir(actuales[+li.dataset.i]); });
  document.addEventListener("click", (e) => { if (!e.target.closest(".buscador")) ul.hidden = true; });
}

// -- enlace permanente (#capas=a,b&fondo=orto&ref=enp) -------------------------------------------
function guardarHash() {
  const capas = Object.values(subcapas).filter((s) => s.activa).map((s) => s.meta.id);
  const ref = [...document.querySelectorAll("#superpuestas input:checked")].map((i) => i.value);
  const h = new URLSearchParams();
  if (capas.length) h.set("capas", capas.join(","));
  if (fondoActual && fondoActual.id !== "orto") h.set("fondo", fondoActual.id);
  if (ref.length) h.set("ref", ref.join(","));
  history.replaceState(null, "", h.toString() ? "#" + h.toString().replace(/%2C/g, ",") : location.pathname + location.search);
}

function leerHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  return { capas: h.get("capas")?.split(",") ?? null, fondo: h.get("fondo"), ref: h.get("ref")?.split(",") ?? [] };
}

// ---------------------------------------------------------------------------------------------
async function iniciar() {
  catalogo = await (await fetch("data/catalogo.json")).json();
  const termino = await (await fetch("data/termino.geojson")).json();
  terminoCapa = L.geoJSON(termino, { interactive: false, style: { color: "#FFD54F", weight: 2.5, fill: false, dashArray: "8 6" } });

  pintarArbol();
  pintarFondos();
  const estado = leerHash();
  ponerFondo(estado.fondo);

  await Promise.all(catalogo.grupos.flatMap((g) => g.subcapas.map(async (s) => {
    subcapas[s.id] = { meta: s, grupo: g, activa: false };
    if (!s.n && !s.sin_ubicacion) return;
    const gj = await (await fetch(`data/${s.id}.geojson`)).json();
    construirCapa(subcapas[s.id], gj);
  })));

  const iniciales = estado.capas ?? catalogo.grupos.flatMap((g) => g.subcapas.filter((s) => s.visible).map((s) => s.id));
  iniciales.forEach((id) => activar(id, true, true));
  catalogo.grupos.forEach((g) => actualizarGrupo(g.id));
  ["termino", ...estado.ref].forEach((id) => {
    const cb = document.querySelector(`#superpuestas input[value="${id}"]`);
    if (cb && !cb.checked) { cb.checked = true; cb.dispatchEvent(new Event("change", { bubbles: true })); }
  });
  if (!estado.capas) $("#g-mar").classList.add("abierto");
  else new Set(iniciales.map((id) => subcapas[id]?.grupo.id)).forEach((g) => g && $("#g-" + g)?.classList.add("abierto"));
  if (innerWidth <= 720) document.body.classList.add("sin-panel");
  mapa.fitBounds(terminoCapa.getBounds(), { padding: [10, 10] });

  // diálogo de información y fuentes
  const fuentes = new Set();
  catalogo.grupos.forEach((g) => g.subcapas.forEach((s) => s.fuente.split(/;\s*/).forEach((f) => fuentes.add(f))));
  ["Ortofoto PNOA (máxima actualidad y 2020), IGN Base y MTN © Instituto Geográfico Nacional (CC BY 4.0)",
   "Espacios protegidos y Red Natura 2000: REDIAM, Junta de Andalucía"].forEach((f) => fuentes.add(f));
  const nSub = catalogo.grupos.reduce((a, g) => a + g.subcapas.length, 0);
  $("#txtCapas").textContent = `Recursos de Marbella en ${catalogo.grupos.length} capas y ${nSub} subcapas: ` +
    catalogo.grupos.map((g) => g.titulo).join(", ").replace(/, ([^,]*)$/, " y $1") + ".";
  $("#listaFuentes").innerHTML = [...fuentes].map((f) => `<li>${esc(f)}</li>`).join("");
  $("#fechaDatos").textContent = `Datos generados el ${new Date(catalogo.generado).toLocaleDateString("es-ES", { day: "numeric", month: "long", year: "numeric" })}.`;
}

$("#btnPanel").addEventListener("click", () => {
  document.body.classList.toggle("sin-panel");
  $("#btnPanel").setAttribute("aria-expanded", !document.body.classList.contains("sin-panel"));
  setTimeout(() => mapa.invalidateSize(), 220);
});
$("#btnInfo").addEventListener("click", () => $("#dlgInfo").showModal());
$("#lnkFuentes").addEventListener("click", (e) => { e.preventDefault(); $("#dlgInfo").showModal(); });
$("#btnNinguna").addEventListener("click", () => { Object.keys(subcapas).forEach((id) => activar(id, false, true)); guardarHash(); });

buscador();
iniciar().catch((e) => { console.error(e); $("#resumen").textContent = "No se han podido cargar los datos del visor."; });
