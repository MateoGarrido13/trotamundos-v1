// SPEC: SPEC-COMP-03
// ELEMENTO PASO 5: Cliente móvil con módulo local de proximidad GPS (ITERACION_5)
// DRIVERS: CON-01, QA-PER-03, QA-USA-01, REF-07, QA-PER-01, REF-03
// El GPS se pide al abrir un viaje, nunca en el login. Las coordenadas no salen del dispositivo.
"use strict";

const PANTALLAS = ["ingreso", "viajes", "viaje", "novedades", "agencia", "revision", "asistente", "error-401"];
const MENU = ["consultar_estado", "reprogramar", "derivar_a_la_agencia"];
const estado = {itinerario: null, viaje: null, reservas: [], posicion: null, vigia: null, contexto: null, repetir: null};
const claves = new Map();

function clave(id) {
  if (!claves.has(id)) claves.set(id, crypto.randomUUID());
  return claves.get(id);
}
function soltar(id) { if (id) claves.delete(id); }

const sesion = {
  guardar(datos) { sessionStorage.setItem("trotamundos.sesion", JSON.stringify(datos)); },
  leer() {
    const crudo = sessionStorage.getItem("trotamundos.sesion");
    return crudo ? JSON.parse(crudo) : null;
  },
  token() { const actual = this.leer(); return actual ? actual.token_acceso : null; },
  borrar() { sessionStorage.removeItem("trotamundos.sesion"); },
};

// Ids internos (viaje-3f9a…, res-…) se muestran acortados; el id completo queda en title/aria-label.
const ROTULOS_ID = {viaje: "Viaje", itin: "Itinerario", res: "Reserva", caso: "Caso"};
function legible(id) {
  const m = /^(viaje|itin|res|caso)-([0-9a-f]{6,})$/i.exec(String(id));
  return m ? ROTULOS_ID[m[1].toLowerCase()] + " #" + m[2].slice(0, 6) : String(id);
}
function cambiosLegibles(cambios) {
  if (!cambios || typeof cambios !== "object") return String(cambios == null ? "" : cambios);
  return Object.entries(cambios)
    .map(([campo, valor]) => campo.replace(/_/g, " ") + ": " + (typeof valor === "object" ? JSON.stringify(valor) : valor))
    .join(" · ");
}

function nodo(etiqueta, valor) {
  const el = document.createElement(etiqueta);
  if (valor != null) el.textContent = String(valor);
  return el;
}
function limpiar(el) { while (el.firstChild) el.removeChild(el.firstChild); }

function lugarDe(valor) {
  if (!valor) return {nombre: "", destino: null, latitud: null, longitud: null};
  if (typeof valor === "string") return {nombre: valor, destino: null, latitud: null, longitud: null};
  return {nombre: valor.nombre || "", destino: valor.destino || null,
          latitud: valor.latitud ?? null, longitud: valor.longitud ?? null};
}

function distanciaMetros(aqui, alla) {
  const r = Math.PI / 180;
  const dLat = (alla.latitud - aqui.latitude) * r;
  const dLon = (alla.longitud - aqui.longitude) * r;
  const s = Math.sin(dLat / 2) ** 2
    + Math.cos(aqui.latitude * r) * Math.cos(alla.latitud * r) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.sqrt(s));
}

function mostrar(id) {
  for (const pantalla of PANTALLAS) document.getElementById(pantalla).hidden = pantalla !== id;
  document.getElementById("menu").hidden = !sesion.token();
  if (id === "viajes") cargarViajes();
  if (id === "novedades") cargarNovedades();
  if (id === "revision") cargarRevision();
  if (id === "viaje") pedirPosicion();
}

function avisar(mensaje) {
  const aviso = document.getElementById("aviso");
  aviso.textContent = mensaje;
  aviso.hidden = false;
  document.getElementById("reintentar").hidden = false;
}
function limpiarAviso() {
  document.getElementById("aviso").hidden = true;
  document.getElementById("reintentar").hidden = true;
  estado.repetir = null;
}

async function pedir(path, opciones) {
  const opts = opciones || {};
  const headers = new Headers();
  const token = sesion.token();
  if (token) headers.set("Authorization", "Bearer " + token);
  if (opts.clave) headers.set("X-Clave-Operacion", opts.clave);
  let cuerpo;
  if (opts.cuerpo !== undefined) {
    headers.set("Content-Type", "application/json");
    cuerpo = JSON.stringify(opts.cuerpo);
  }
  try {
    const respuesta = await fetch(path, {method: opts.metodo || "GET", headers, body: cuerpo});
    if (respuesta.status === 503 || respuesta.status === 504) {
      if (path.startsWith("/asistente/")) pintarMenu(MENU);
      estado.repetir = opts.repetir || null;
      avisar("Servicio no disponible. Se conserva lo que ya ves. Podés reintentar.");
      return respuesta;
    }
    if (respuesta.status === 403) {
      let detalle = {};
      try { detalle = await respuesta.clone().json(); } catch (_e) { detalle = {}; }
      if (detalle.error === "acceso_denegado") {
        mostrar("error-401");
        return respuesta;
      }
    }
    if (respuesta.ok) soltar(opts.accion);
    return respuesta;
  } catch (_error) {
    estado.repetir = opts.repetir || null;
    avisar("Servicio no disponible. Se conserva lo que ya ves. Podés reintentar.");
    return null;
  }
}

async function jsonOk(respuesta) {
  if (!respuesta || !respuesta.ok) return null;
  if (respuesta.status === 204) return {};
  return respuesta.json();
}

async function autenticar(ruta) {
  document.getElementById("ingreso-nota").textContent = "";
  let respuesta;
  try {
    respuesta = await fetch(ruta, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        correo: document.getElementById("correo-cuenta").value,
        contrasena: document.getElementById("contrasena").value,
        region: document.getElementById("region").value,
      }),
    });
  } catch (_error) {
    avisar("Servicio no disponible. Se conserva lo que ya ves. Podés reintentar.");
    estado.repetir = () => autenticar(ruta);
    return;
  }
  if (!respuesta.ok) {
    document.getElementById("ingreso-nota").textContent = "No se pudo ingresar.";
    return;
  }
  const datos = await respuesta.json();
  sesion.guardar(datos);
  const cuenta = document.getElementById("cuenta");
  cuenta.textContent = datos.cuenta_id;
  cuenta.hidden = false;
  limpiarAviso();
  mostrar("viajes");
}

function salir() {
  sesion.borrar();
  if (estado.vigia != null && navigator.geolocation) navigator.geolocation.clearWatch(estado.vigia);
  estado.vigia = null;
  estado.posicion = null;
  document.getElementById("cuenta").hidden = true;
  document.getElementById("menu").hidden = true;
  mostrar("ingreso");
}

async function cargarViajes() {
  const lista = await pedir("/itinerarios", {repetir: cargarViajes});
  const itinerarios = await jsonOk(lista);
  if (!itinerarios) return;
  const arbol = document.getElementById("arbol-viajes");
  limpiar(arbol);
  for (const itin of itinerarios) {
    const detalle = await pedir("/itinerarios/" + encodeURIComponent(itin.id));
    const viajes = await jsonOk(detalle);
    if (!viajes) return;
    const bloque = nodo("div");
    bloque.append(nodo("h2", legible(itin.id)));
    for (const viaje of viajes) {
      bloque.append(nodo("h3", legible(viaje.id)));
      const abrir = nodo("button", "Abrir viaje");
      abrir.type = "button";
      abrir.addEventListener("click", () => abrirViaje(itin.id, viaje));
      bloque.append(abrir);
    }
    arbol.append(bloque);
  }
}

async function crearViaje(evento) {
  evento.preventDefault();
  const id = "alta-viaje";
  const respuesta = await pedir("/viajes", {
    metodo: "POST", cuerpo: {nombre: document.getElementById("viaje-nombre").value},
    clave: clave(id), accion: id, repetir: () => crearViaje(evento),
  });
  const datos = await jsonOk(respuesta);
  if (!datos) return;
  estado.itinerario = datos.itinerario_id;
  document.getElementById("form-viaje").reset();
  limpiarAviso();
  await cargarViajes();
}

function abrirViaje(itinerarioId, viaje) {
  estado.itinerario = itinerarioId;
  estado.viaje = viaje.id;
  estado.reservas = (viaje.reservas || []).map((reserva) => ({...reserva, lugar: lugarDe(reserva.lugar)}));
  document.getElementById("viaje-titulo").textContent = legible(viaje.id);
  for (const pantalla of PANTALLAS) document.getElementById(pantalla).hidden = pantalla !== "viaje";
  document.getElementById("menu").hidden = false;
  pintarReservas();
  pedirPosicion();
}

function pedirPosicion() {
  if (document.getElementById("viaje").hidden) return;
  if (!navigator.geolocation) return;
  if (estado.vigia != null) return;
  estado.vigia = navigator.geolocation.watchPosition(
    (pos) => {
      estado.posicion = {latitude: pos.coords.latitude, longitude: pos.coords.longitude};
      pintarReservas();
    },
    () => { estado.posicion = null; pintarReservas(); },
  );
}

function pintarReservas() {
  const caja = document.getElementById("lista-reservas");
  const ordenadas = estado.reservas.slice().sort((a, b) => String(a.inicio).localeCompare(String(b.inicio)));
  let cercana = null;
  if (estado.posicion) {
    for (const reserva of ordenadas) {
      if (reserva.lugar.latitud == null) continue;
      const metros = distanciaMetros(estado.posicion, reserva.lugar);
      if (!cercana || metros < cercana.metros) cercana = {id: reserva.identificador, metros};
    }
  }
  limpiar(caja);
  for (const reserva of ordenadas) {
    const fila = nodo("div");
    fila.className = "reserva";
    const lugar = reserva.lugar;
    fila.append(nodo("p", (reserva.resumen || lugar.nombre) + (lugar.destino ? " · " + lugar.destino : "")));
    if (estado.posicion && lugar.latitud != null) {
      const metros = Math.round(distanciaMetros(estado.posicion, lugar));
      fila.append(nodo("p", metros + " m"));
      const ruta = nodo("a", "Cómo llegar");
      ruta.href = "geo:" + lugar.latitud + "," + lugar.longitud;
      fila.append(ruta);
      if (cercana && cercana.id === reserva.identificador) {
        fila.classList.add("cercana");
        fila.append(nodo("p", "más cercana"));
      }
    }
    const baja = nodo("button", "Dar de baja " + legible(reserva.identificador));
    baja.setAttribute("aria-label", "Dar de baja " + reserva.identificador);
    baja.title = reserva.identificador;
    baja.type = "button";
    baja.addEventListener("click", () => eliminarReserva(reserva.identificador));
    fila.append(baja);
    caja.append(fila);
  }
}

function lugarDelFormulario() {
  const nombre = document.getElementById("lugar-nombre").value;
  const destino = document.getElementById("lugar-destino").value.trim();
  const latitud = document.getElementById("lugar-latitud").value.trim();
  const longitud = document.getElementById("lugar-longitud").value.trim();
  if (!destino && !latitud && !longitud) return nombre;
  const lugar = {nombre, destino: destino || null, latitud: null, longitud: null};
  if (latitud || longitud) {
    lugar.latitud = Number(latitud);
    lugar.longitud = Number(longitud);
  }
  return lugar;
}

async function crearReserva(evento) {
  evento.preventDefault();
  const id = "alta-reserva";
  const inicio = document.getElementById("reserva-inicio").value;
  const fin = document.getElementById("reserva-fin").value;
  const respuesta = await pedir("/itinerarios/" + encodeURIComponent(estado.itinerario) + "/reservas", {
    metodo: "POST",
    cuerpo: {
      viaje_id: estado.viaje, tipo: document.getElementById("reserva-tipo").value,
      inicio: inicio.length === 16 ? inicio + ":00" : inicio,
      fin: fin.length === 16 ? fin + ":00" : fin,
      lugar: lugarDelFormulario(), datos: {},
    },
    clave: clave(id), accion: id, repetir: () => crearReserva(evento),
  });
  const datos = await jsonOk(respuesta);
  if (!datos) return;
  const reserva = datos.reserva || datos;
  estado.reservas.push({...reserva, lugar: lugarDe(reserva.lugar)});
  document.getElementById("form-reserva").reset();
  limpiarAviso();
  pintarReservas();
}

async function eliminarReserva(reservaId) {
  const id = "baja-" + reservaId;
  const respuesta = await pedir(
    "/itinerarios/" + encodeURIComponent(estado.itinerario) + "/reservas/" + encodeURIComponent(reservaId),
    {metodo: "DELETE", clave: clave(id), accion: id, repetir: () => eliminarReserva(reservaId)},
  );
  if (!respuesta || !respuesta.ok) return;
  estado.reservas = estado.reservas.filter((reserva) => reserva.identificador !== reservaId);
  limpiarAviso();
  pintarReservas();
}

async function cargarNovedades() {
  if (!estado.itinerario) return;
  const novedades = await pedir("/itinerarios/" + encodeURIComponent(estado.itinerario) + "/novedades");
  const casos = await pedir("/casos");
  const listaN = await jsonOk(novedades);
  const listaC = await jsonOk(casos);
  if (!listaN || !listaC) return;
  const cajaN = document.getElementById("lista-novedades");
  limpiar(cajaN);
  for (const novedad of listaN) cajaN.append(nodo("p", novedad.proveedor + " — " + cambiosLegibles(novedad.cambios)));
  const cajaC = document.getElementById("lista-casos");
  limpiar(cajaC);
  for (const caso of listaC) {
    const fila = nodo("div");
    fila.append(nodo("p", legible(caso.id) + " · " + caso.estado.replace(/_/g, " ")));
    if (caso.estado === "sin_entregar") {
      const boton = nodo("button", "Reintentar caso");
      boton.type = "button";
      boton.addEventListener("click", () => reintentar(caso));
      fila.append(boton);
    }
    cajaC.append(fila);
  }
}

async function reintentar(caso) {
  const respuesta = await pedir("/casos/" + encodeURIComponent(caso.id) + "/reintentar", {
    metodo: "POST", cuerpo: {itinerario_id: caso.itinerario_id},
    clave: clave("reintentar-" + caso.id), accion: "reintentar-" + caso.id,
    repetir: () => reintentar(caso),
  });
  if (!respuesta || !respuesta.ok) return;
  limpiarAviso();
  await cargarNovedades();
}

async function guardarAgencia(evento) {
  evento.preventDefault();
  if (!document.getElementById("consentimiento").checked) {
    document.getElementById("falta-agencia").hidden = false;
    return;
  }
  const respuesta = await pedir("/agencia-preferida", {
    metodo: "PUT",
    cuerpo: {agencia: document.getElementById("agencia-nombre").value, consentimiento: true},
    repetir: () => guardarAgencia(evento),
  });
  if (!respuesta || !respuesta.ok) return;
  document.getElementById("falta-agencia").hidden = true;
  limpiarAviso();
}

async function reportar(evento) {
  evento.preventDefault();
  const agencia = await jsonOk(await pedir("/agencia-preferida"));
  if (!agencia || !agencia.agencia || !document.getElementById("consentimiento").checked) {
    document.getElementById("falta-agencia").hidden = false;
    return;
  }
  const respuesta = await pedir("/casos", {
    metodo: "POST",
    cuerpo: {
      itinerario_id: estado.itinerario,
      reserva_id: document.getElementById("problema-reserva").textContent,
      descripcion: document.getElementById("problema-descripcion").value,
    },
    clave: clave("reportar"), accion: "reportar", repetir: () => reportar(evento),
  });
  if (!respuesta || !respuesta.ok) return;
  limpiarAviso();
  mostrar("novedades");
}

async function cargarRevision() {
  const mensajes = await jsonOk(await pedir("/revision"));
  if (!mensajes) return;
  const caja = document.getElementById("lista-revision");
  limpiar(caja);
  for (const mensaje of mensajes) {
    const fila = nodo("div");
    fila.append(nodo("p", mensaje.remitente + " — " + mensaje.resumen));
    const aprobar = nodo("button", "Aprobar " + mensaje.remitente);
    aprobar.type = "button";
    aprobar.addEventListener("click", async () => {
      const respuesta = await pedir("/revision/remitentes", {metodo: "POST", cuerpo: {remitente: mensaje.remitente}});
      if (respuesta && respuesta.ok) cargarRevision();
    });
    fila.append(aprobar);
    caja.append(fila);
  }
}

function pintarMenu(items) {
  const menu = document.getElementById("asistente-menu");
  limpiar(menu);
  for (const item of items) {
    const boton = nodo("button", item);
    boton.type = "button";
    boton.addEventListener("click", () => enviarAccion({tipo: item}));
    menu.append(boton);
  }
}

function pintarAsistente(datos) {
  const caja = document.getElementById("asistente-respuesta");
  limpiar(caja);
  caja.append(nodo("p", datos.texto || ""));
  pintarMenu(datos.menu || []);
  if (datos.contexto) estado.contexto = datos.contexto;
  limpiarAviso();
}

async function enviarTurno(evento) {
  evento.preventDefault();
  const respuesta = await pedir("/asistente/turno", {
    metodo: "POST",
    cuerpo: {itinerario_id: estado.itinerario, mensaje: document.getElementById("asistente-mensaje").value, contexto: estado.contexto},
    repetir: () => enviarTurno(evento),
  });
  const datos = await jsonOk(respuesta);
  if (datos) pintarAsistente(datos);
}

async function enviarAccion(accion) {
  const respuesta = await pedir("/asistente/accion", {
    metodo: "POST",
    cuerpo: {itinerario_id: estado.itinerario, accion, contexto: estado.contexto},
  });
  const datos = await jsonOk(respuesta);
  if (datos) pintarAsistente(datos);
}

document.getElementById("form-ingreso").addEventListener("submit", (evento) => {
  evento.preventDefault();
  autenticar("/auth/login");
});
document.getElementById("crear-cuenta").addEventListener("click", () => autenticar("/auth/alta"));
document.getElementById("salir").addEventListener("click", salir);
document.getElementById("form-viaje").addEventListener("submit", crearViaje);
document.getElementById("form-reserva").addEventListener("submit", crearReserva);
document.getElementById("form-agencia").addEventListener("submit", guardarAgencia);
document.getElementById("form-problema").addEventListener("submit", reportar);
document.getElementById("form-asistente").addEventListener("submit", enviarTurno);
document.getElementById("volver-viajes").addEventListener("click", () => mostrar("viajes"));
document.getElementById("reintentar").addEventListener("click", () => { if (estado.repetir) estado.repetir(); });
for (const boton of document.querySelectorAll("#menu button[data-pantalla]")) {
  boton.addEventListener("click", () => mostrar(boton.dataset.pantalla));
}
window.addEventListener("load", () => {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/movil/sw.js");
});
