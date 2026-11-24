// SPEC: SPEC-COMP-02
// ELEMENTO PASO 5: Cliente web (ITERACION_1, ITERACION_3, RONDA_2/ITERACION_1)
// DRIVERS: CON-01, REF-01, REF-03, REF-04, REF-05, REF-07, QA-SEG-02, QA-PER-01, QA-PER-02
// El cliente solo habla con esta app. No decide permisos ni inserta HTML del backend.
"use strict";

const PANTALLAS = ["ingreso", "viajes", "viaje", "miembros", "novedades", "agencia", "revision", "correo", "asistente", "cotizacion", "error-401"];
const REFRESCO_NOVEDADES_MS = Number(document.querySelector('meta[name="trotamundos-refresco-novedades"]').content) * 1000;
const MENU_GUIADO = ["consultar_estado", "reprogramar", "derivar_a_la_agencia"];
const ESTADOS_CASO = {
  sin_entregar: "sin entregar",
  en_tramite: "en trámite",
  abierto: "abierto",
  en_curso: "en curso",
  resuelto: "resuelto",
};

const estado = {
  itinerario: null,
  viaje: null,
  reservaProblema: null,
  repetir: null,
  contexto: {},
  grilla: null,
};

const claves = new Map();
let relojNovedades = null;

function clave(id) {
  if (!claves.has(id)) claves.set(id, crypto.randomUUID());
  return claves.get(id);
}

function soltar(id) {
  if (id) claves.delete(id);
}

const sesion = {
  guardar(datos) {
    sessionStorage.setItem("trotamundos.sesion", JSON.stringify(datos));
  },
  leer() {
    const crudo = sessionStorage.getItem("trotamundos.sesion");
    return crudo ? JSON.parse(crudo) : null;
  },
  token() {
    const actual = this.leer();
    return actual ? actual.token_acceso : null;
  },
  borrar() {
    sessionStorage.removeItem("trotamundos.sesion");
  },
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

function texto(padre, etiqueta, valor) {
  const nodo = document.createElement(etiqueta);
  nodo.textContent = valor == null ? "" : String(valor);
  padre.append(nodo);
  return nodo;
}

function limpiar(nodo) {
  while (nodo.firstChild) nodo.removeChild(nodo.firstChild);
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

function mostrarMenuGuiado() {
  const menu = document.getElementById("asistente-menu");
  limpiar(menu);
  for (const item of MENU_GUIADO) {
    const boton = texto(menu, "button", item);
    boton.type = "button";
    boton.addEventListener("click", () => enviarAccion({tipo: item}));
  }
}

function mostrar(id) {
  for (const pantalla of PANTALLAS) {
    document.getElementById(pantalla).hidden = pantalla !== id;
  }
  const conSesion = id !== "ingreso" && id !== "error-401";
  document.getElementById("menu").hidden = !conSesion && id !== "error-401" ? !sesion.token() : !sesion.token();
  if (sesion.token() && id !== "ingreso") document.getElementById("menu").hidden = false;
  vigilarNovedades(id === "novedades");
  if (id === "viajes") cargarViajes();
  if (id === "miembros") cargarMiembros();
  if (id === "revision") cargarRevision();
  if (id === "agencia") cargarAgencia();
  if (id === "asistente" || id === "novedades" || id === "miembros") cargarSelectorItinerarios();
}

function vigilarNovedades(activo) {
  if (relojNovedades) clearInterval(relojNovedades);
  relojNovedades = null;
  if (activo) {
    cargarNovedades();
    relojNovedades = setInterval(cargarNovedades, REFRESCO_NOVEDADES_MS);
  }
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
      if (path.startsWith("/asistente/")) mostrarMenuGuiado();
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

async function leerJson(respuesta) {
  if (!respuesta || !respuesta.ok) return null;
  if (respuesta.status === 204) return {};
  return respuesta.json();
}

function isoLocal(valor) {
  if (!valor) return valor;
  return valor.length === 16 ? valor + ":00" : valor;
}

async function autenticar(ruta) {
  const nota = document.getElementById("ingreso-nota");
  nota.textContent = "";
  const cuerpo = {
    correo: document.getElementById("correo-cuenta").value,
    contrasena: document.getElementById("contrasena").value,
    region: document.getElementById("region").value,
  };
  let respuesta;
  try {
    respuesta = await fetch(ruta, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(cuerpo),
    });
  } catch (_error) {
    avisar("Servicio no disponible. Se conserva lo que ya ves. Podés reintentar.");
    estado.repetir = () => autenticar(ruta);
    return;
  }
  if (respuesta.status === 401) {
    nota.textContent = "Credenciales inválidas.";
    return;
  }
  if (!respuesta.ok) {
    nota.textContent = "No se pudo ingresar.";
    return;
  }
  entrarCon(await respuesta.json());
}

function entrarCon(datos) {
  sesion.guardar(datos);
  const cuenta = document.getElementById("cuenta");
  cuenta.textContent = datos.cuenta_id;
  cuenta.hidden = false;
  limpiarAviso();
  mostrar("viajes");
}

function salir() {
  sesion.borrar();
  claves.clear();
  estado.itinerario = null;
  document.getElementById("cuenta").hidden = true;
  document.getElementById("menu").hidden = true;
  limpiarAviso();
  mostrar("ingreso");
}

async function cargarViajes() {
  const lista = await pedir("/itinerarios", {repetir: cargarViajes});
  if (!lista || !lista.ok) return;
  const itinerarios = await lista.json();
  const vista = await pedir("/viajes", {repetir: cargarViajes});
  if (!vista || !vista.ok) return;
  const viajesCuenta = await vista.json();
  const detalles = [];
  for (const itin of itinerarios) {
    const detalle = await pedir("/itinerarios/" + encodeURIComponent(itin.id), {repetir: cargarViajes});
    if (!detalle || !detalle.ok) return;
    detalles.push({itin, viajes: await detalle.json()});
  }
  const arbol = document.getElementById("arbol-viajes");
  limpiar(arbol);
  const yaMostrados = new Set(detalles.flatMap((item) => item.viajes.map((viaje) => viaje.id)));
  const sueltos = viajesCuenta.filter((viaje) => !yaMostrados.has(viaje.id));
  if (sueltos.length) {
    const bloque = texto(arbol, "div", "");
    bloque.className = "itinerario";
    texto(bloque, "h2", "Vista principal");
    pintarViajes(bloque, sueltos, null);
  }
  for (const item of detalles) {
    const bloque = texto(arbol, "div", "");
    bloque.className = "itinerario";
    bloque.dataset.itinerario = item.itin.id;
    texto(bloque, "h2", legible(item.itin.id) + " · " + item.itin.rol).title = item.itin.id;
    pintarViajes(bloque, item.viajes, item.itin.id);
    const gestionar = texto(bloque, "button", "Gestionar");
    gestionar.type = "button";
    gestionar.addEventListener("click", () => abrirViaje(item.itin.id, item.viajes));
  }
}

function pintarViajes(bloque, viajes, itinerarioId) {
  for (const viaje of viajes) {
    const caja = texto(bloque, "div", "");
    caja.className = "viaje";
    texto(caja, "h3", legible(viaje.id)).title = viaje.id;
    const lista = texto(caja, "ul", "");
    for (const reserva of viaje.reservas) {
      texto(lista, "li", reserva.resumen || reserva.lugar || reserva.identificador);
    }
    if (itinerarioId && viaje.reservas) {
      for (const reserva of viaje.reservas) {
        const baja = texto(caja, "button", "Dar de baja " + legible(reserva.identificador));
        baja.setAttribute("aria-label", "Dar de baja " + reserva.identificador);
        baja.title = reserva.identificador;
        baja.type = "button";
        baja.addEventListener("click", () => eliminarReserva(itinerarioId, reserva.identificador));
        const problema = texto(caja, "button", "Reportar problema " + legible(reserva.identificador));
        problema.setAttribute("aria-label", "Reportar problema " + reserva.identificador);
        problema.title = reserva.identificador;
        problema.type = "button";
        problema.addEventListener("click", () => prepararProblema(itinerarioId, reserva.identificador));
      }
    }
  }
}

function abrirViaje(itinerarioId, viajes) {
  estado.itinerario = itinerarioId;
  estado.viaje = viajes && viajes.length ? viajes[0].id : null;
  document.getElementById("viaje-titulo").textContent = legible(itinerarioId);
  const caja = document.getElementById("reservas-viaje");
  limpiar(caja);
  pintarViajes(caja, viajes || [], itinerarioId);
  mostrarSeccion("viaje");
}

function mostrarSeccion(id) {
  for (const pantalla of PANTALLAS) document.getElementById(pantalla).hidden = pantalla !== id;
  document.getElementById("menu").hidden = false;
  vigilarNovedades(id === "novedades");
}

async function crearViaje(evento) {
  evento.preventDefault();
  const id = "alta-viaje";
  const nombre = document.getElementById("viaje-nombre").value;
  const respuesta = await pedir("/viajes", {
    metodo: "POST",
    cuerpo: {nombre},
    clave: clave(id),
    accion: id,
    repetir: () => crearViaje(evento),
  });
  const datos = await leerJson(respuesta);
  if (!datos) return;
  estado.itinerario = datos.itinerario_id;
  document.getElementById("form-viaje").reset();
  limpiarAviso();
  await cargarViajes();
}

async function crearReserva(evento) {
  evento.preventDefault();
  const id = "alta-reserva";
  const cuerpo = {
    viaje_id: estado.viaje || ("viaje-" + (estado.itinerario || "nuevo")),
    tipo: document.getElementById("reserva-tipo").value,
    inicio: isoLocal(document.getElementById("reserva-inicio").value),
    fin: isoLocal(document.getElementById("reserva-fin").value),
    lugar: document.getElementById("reserva-lugar").value,
    datos: {},
  };
  const respuesta = await pedir("/itinerarios/" + encodeURIComponent(estado.itinerario) + "/reservas", {
    metodo: "POST",
    cuerpo,
    clave: clave(id),
    accion: id,
    repetir: () => crearReserva({preventDefault() {}}),
  });
  if (!respuesta || !respuesta.ok) return;
  document.getElementById("form-reserva").reset();
  limpiarAviso();
  await pintarReservasAbiertas();
}

async function pintarReservasAbiertas() {
  if (!estado.itinerario) return;
  const respuesta = await pedir("/itinerarios/" + encodeURIComponent(estado.itinerario));
  const viajes = await leerJson(respuesta);
  if (!viajes) return;
  const caja = document.getElementById("reservas-viaje");
  limpiar(caja);
  pintarViajes(caja, viajes, estado.itinerario);
  document.getElementById("viaje-titulo").textContent = legible(estado.itinerario);
}

async function eliminarReserva(itinerarioId, reservaId) {
  const id = "baja-" + reservaId;
  const respuesta = await pedir(
    "/itinerarios/" + encodeURIComponent(itinerarioId) + "/reservas/" + encodeURIComponent(reservaId),
    {metodo: "DELETE", clave: clave(id), accion: id, repetir: () => eliminarReserva(itinerarioId, reservaId)},
  );
  if (!respuesta || !respuesta.ok) return;
  limpiarAviso();
  await cargarViajes();
}

async function verArchivados() {
  const respuesta = await pedir("/viajes/archivados", {repetir: verArchivados});
  const viajes = await leerJson(respuesta);
  if (!viajes) return;
  const caja = document.getElementById("archivados");
  limpiar(caja);
  texto(caja, "h2", "Archivados");
  pintarViajes(caja, viajes, null);
}

async function cargarSelectorItinerarios() {
  const respuesta = await pedir("/itinerarios");
  const lista = await leerJson(respuesta);
  if (!lista) return;
  for (const id of ["novedades-itinerario", "asistente-itinerario"]) {
    const select = document.getElementById(id);
    const previo = select.value || estado.itinerario;
    limpiar(select);
    for (const itin of lista) {
      const opcion = texto(select, "option", legible(itin.id));
      opcion.value = itin.id;
    }
    if (previo) select.value = previo;
    if (!estado.itinerario && lista.length) estado.itinerario = lista[0].id;
  }
}

async function cargarMiembros() {
  await cargarSelectorItinerarios();
  const itinerario = estado.itinerario || document.getElementById("novedades-itinerario").value;
  if (!itinerario) return;
  estado.itinerario = itinerario;
  const respuesta = await pedir("/itinerarios/" + encodeURIComponent(itinerario) + "/miembros", {repetir: cargarMiembros});
  const miembros = await leerJson(respuesta);
  if (!miembros) return;
  const caja = document.getElementById("lista-miembros");
  limpiar(caja);
  texto(caja, "p", legible(itinerario));
  for (const miembro of miembros) {
    const fila = texto(caja, "div", "");
    fila.className = "fila";
    texto(fila, "span", miembro.cuenta + " — " + miembro.rol);
    const quitar = texto(fila, "button", "Quitar " + miembro.cuenta);
    quitar.type = "button";
    quitar.addEventListener("click", () => quitarMiembro(itinerario, miembro.cuenta));
  }
}

async function agregarMiembro(evento) {
  evento.preventDefault();
  const id = "alta-miembro";
  const respuesta = await pedir("/itinerarios/" + encodeURIComponent(estado.itinerario) + "/miembros", {
    metodo: "POST",
    cuerpo: {
      cuenta: document.getElementById("miembro-cuenta").value,
      rol: document.getElementById("miembro-rol").value,
    },
    clave: clave(id),
    accion: id,
    repetir: () => agregarMiembro(evento),
  });
  if (!respuesta || !respuesta.ok) return;
  document.getElementById("form-miembro").reset();
  limpiarAviso();
  await cargarMiembros();
}

async function quitarMiembro(itinerario, cuenta) {
  const id = "quitar-" + cuenta;
  const respuesta = await pedir(
    "/itinerarios/" + encodeURIComponent(itinerario) + "/miembros/" + encodeURIComponent(cuenta),
    {metodo: "DELETE", clave: clave(id), accion: id, repetir: () => quitarMiembro(itinerario, cuenta)},
  );
  if (!respuesta || !respuesta.ok) return;
  limpiarAviso();
  await cargarMiembros();
}

async function cargarNovedades() {
  const select = document.getElementById("novedades-itinerario");
  const itinerario = select.value || estado.itinerario;
  if (!itinerario) return;
  estado.itinerario = itinerario;
  const novedades = await pedir("/itinerarios/" + encodeURIComponent(itinerario) + "/novedades", {repetir: cargarNovedades});
  const casos = await pedir("/casos", {repetir: cargarNovedades});
  if (!novedades || !novedades.ok || !casos || !casos.ok) return;
  const listaN = await novedades.json();
  const listaC = await casos.json();
  const cajaN = document.getElementById("lista-novedades");
  limpiar(cajaN);
  for (const novedad of listaN) {
    texto(cajaN, "p", novedad.proveedor + " — " + cambiosLegibles(novedad.cambios));
  }
  const cajaC = document.getElementById("lista-casos");
  limpiar(cajaC);
  for (const caso of listaC) {
    const fila = texto(cajaC, "div", "");
    fila.className = "fila";
    texto(fila, "p", legible(caso.id) + " · " + (ESTADOS_CASO[caso.estado] || caso.estado)).title = caso.id;
    if (caso.estado === "sin_entregar") {
      const boton = texto(fila, "button", "Reintentar caso");
      boton.type = "button";
      boton.addEventListener("click", () => reintentarCaso(caso.id, caso.itinerario_id));
    }
  }
}

async function reintentarCaso(casoId, itinerarioId) {
  const id = "reintentar-" + casoId;
  const respuesta = await pedir("/casos/" + encodeURIComponent(casoId) + "/reintentar", {
    metodo: "POST",
    cuerpo: {itinerario_id: itinerarioId},
    clave: clave(id),
    accion: id,
    repetir: () => reintentarCaso(casoId, itinerarioId),
  });
  if (!respuesta || !respuesta.ok) return;
  limpiarAviso();
  await cargarNovedades();
}

async function cargarAgencia() {
  const respuesta = await pedir("/agencia-preferida", {repetir: cargarAgencia});
  const datos = await leerJson(respuesta);
  if (!datos) return;
  document.getElementById("agencia-actual").textContent = datos.agencia
    ? "Agencia preferida: " + datos.agencia
    : "Sin agencia preferida";
  document.getElementById("falta-agencia").hidden = Boolean(datos.agencia);
}

async function prepararProblema(itinerarioId, reservaId) {
  estado.itinerario = itinerarioId;
  estado.reservaProblema = reservaId;
  document.getElementById("problema-reserva").textContent = legible(reservaId);
  mostrarSeccion("agencia");
  await cargarAgencia();
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
  limpiarAviso();
  await cargarAgencia();
}

async function reportarProblema(evento) {
  evento.preventDefault();
  const agencia = await pedir("/agencia-preferida");
  const datos = await leerJson(agencia);
  if (!datos || !datos.agencia || !document.getElementById("consentimiento").checked) {
    document.getElementById("falta-agencia").hidden = false;
    document.getElementById("problema-datos").hidden = false;
    mostrarSeccion("agencia");
    return;
  }
  const id = "reportar-" + estado.reservaProblema;
  const respuesta = await pedir("/casos", {
    metodo: "POST",
    cuerpo: {
      itinerario_id: estado.itinerario,
      reserva_id: estado.reservaProblema,
      descripcion: document.getElementById("problema-descripcion").value,
    },
    clave: clave(id),
    accion: id,
    repetir: () => reportarProblema(evento),
  });
  if (!respuesta || !respuesta.ok) return;
  limpiarAviso();
  mostrar("novedades");
}

async function cargarRevision() {
  const respuesta = await pedir("/revision", {repetir: cargarRevision});
  const mensajes = await leerJson(respuesta);
  if (!mensajes) return;
  const caja = document.getElementById("lista-revision");
  limpiar(caja);
  for (const mensaje of mensajes) {
    const fila = texto(caja, "div", "");
    fila.className = "fila";
    texto(fila, "p", mensaje.remitente + " — " + mensaje.resumen);
    const aprobar = texto(fila, "button", "Aprobar " + mensaje.remitente);
    aprobar.type = "button";
    aprobar.addEventListener("click", () => aprobarRemitente(mensaje.remitente));
    const descartar = texto(fila, "button", "Descartar");
    descartar.setAttribute("aria-label", "Descartar " + mensaje.id_mensaje);
    descartar.title = mensaje.id_mensaje;
    descartar.type = "button";
    descartar.addEventListener("click", () => descartarMensaje(mensaje.id_mensaje));
  }
}

async function aprobarRemitente(remitente) {
  const respuesta = await pedir("/revision/remitentes", {
    metodo: "POST",
    cuerpo: {remitente},
    repetir: () => aprobarRemitente(remitente),
  });
  if (!respuesta || !respuesta.ok) return;
  limpiarAviso();
  await cargarRevision();
  await cargarViajes();
}

async function descartarMensaje(idMensaje) {
  const respuesta = await pedir("/revision/descartar", {
    metodo: "POST",
    cuerpo: {id_mensaje: idMensaje},
    repetir: () => descartarMensaje(idMensaje),
  });
  if (!respuesta || !respuesta.ok) return;
  await cargarRevision();
}

async function quitarRemitente() {
  const remitente = document.getElementById("remitente-seguro").value;
  const respuesta = await pedir("/revision/remitentes/" + encodeURIComponent(remitente), {
    metodo: "DELETE",
    repetir: quitarRemitente,
  });
  if (!respuesta || !respuesta.ok) return;
  await cargarRevision();
}

async function autorizarCorreo(evento) {
  evento.preventDefault();
  const respuesta = await pedir("/correo/autorizacion", {
    metodo: "POST",
    cuerpo: {token: document.getElementById("correo-token").value},
    repetir: () => autorizarCorreo(evento),
  });
  const datos = await leerJson(respuesta);
  if (!datos) return;
  document.getElementById("correo-estado").textContent = "Autorizado hasta " + (datos.vence || "");
  limpiarAviso();
}

async function revocarCorreo() {
  const respuesta = await pedir("/correo/autorizacion", {metodo: "DELETE", repetir: revocarCorreo});
  if (!respuesta || !respuesta.ok) return;
  document.getElementById("correo-estado").textContent = "Autorización revocada";
  limpiarAviso();
}

function itinerarioAsistente() {
  return document.getElementById("asistente-itinerario").value || estado.itinerario;
}

function pintarAsistente(datos) {
  const caja = document.getElementById("asistente-respuesta");
  limpiar(caja);
  texto(caja, "p", datos.texto || "");
  if (datos.numero_agencia) texto(caja, "p", datos.numero_agencia);
  const menu = document.getElementById("asistente-menu");
  limpiar(menu);
  for (const item of datos.menu || []) {
    const boton = texto(menu, "button", item);
    boton.type = "button";
    boton.addEventListener("click", () => enviarAccion({tipo: item}));
  }
  const propuesta = document.getElementById("asistente-propuesta");
  limpiar(propuesta);
  if (datos.tipo === "propuesta") {
    texto(propuesta, "p", "Hay una acción pendiente. No se ejecuta hasta que confirmes.");
    const confirmar = texto(propuesta, "button", "Confirmar");
    confirmar.type = "button";
    confirmar.addEventListener("click", () => enviarAccion({tipo: "confirmar"}));
    const cancelar = texto(propuesta, "button", "Cancelar acción");
    cancelar.type = "button";
    cancelar.addEventListener("click", () => enviarAccion({tipo: "cancelar"}));
  }
  if (datos.contexto) estado.contexto[itinerarioAsistente()] = datos.contexto;
}

async function enviarTurno(evento) {
  evento.preventDefault();
  const itinerario = itinerarioAsistente();
  const respuesta = await pedir("/asistente/turno", {
    metodo: "POST",
    cuerpo: {
      itinerario_id: itinerario,
      mensaje: document.getElementById("asistente-mensaje").value,
      contexto: estado.contexto[itinerario] || null,
    },
    repetir: () => enviarTurno(evento),
  });
  const datos = await leerJson(respuesta);
  if (!datos) return;
  limpiarAviso();
  pintarAsistente(datos);
}

async function enviarAccion(accion) {
  const itinerario = itinerarioAsistente();
  const respuesta = await pedir("/asistente/accion", {
    metodo: "POST",
    cuerpo: {itinerario_id: itinerario, accion, contexto: estado.contexto[itinerario] || null},
    repetir: () => enviarAccion(accion),
  });
  const datos = await leerJson(respuesta);
  if (!datos) return;
  limpiarAviso();
  pintarAsistente(datos);
}

async function cotizar(evento) {
  evento.preventDefault();
  const params = new URLSearchParams({
    fecha: document.getElementById("cotizacion-fecha").value,
    hospedaje: document.getElementById("cotizacion-hospedaje").value,
    compania: document.getElementById("cotizacion-compania").value,
  });
  const respuesta = await pedir("/cotizaciones?" + params.toString(), {repetir: () => cotizar(evento)});
  if (!respuesta) return;
  if (respuesta.status === 504) return;
  const grilla = await leerJson(respuesta);
  if (!grilla) return;
  estado.grilla = grilla;
  pintarGrilla(grilla);
  limpiarAviso();
}

function pintarGrilla(grilla) {
  const estadoNodo = document.getElementById("cotizacion-estado");
  estadoNodo.textContent = grilla.en_curso ? "Cotización en curso" : "";
  const caja = document.getElementById("grilla");
  limpiar(caja);
  for (const origen of grilla.origenes || []) {
    const fila = texto(caja, "div", "");
    fila.className = "fila";
    const marca = origen.estado === "ok" ? "respondió" : "no respondió";
    texto(fila, "p", origen.proveedor + " " + marca);
    for (const precio of origen.precios || []) {
      texto(fila, "p", precio.descripcion + " " + precio.monto + " " + precio.moneda);
    }
  }
}

document.getElementById("form-ingreso").addEventListener("submit", (evento) => {
  evento.preventDefault();
  autenticar("/auth/login");
});
document.getElementById("crear-cuenta").addEventListener("click", () => autenticar("/auth/alta"));
document.getElementById("salir").addEventListener("click", salir);
document.getElementById("form-viaje").addEventListener("submit", crearViaje);
document.getElementById("actualizar-viajes").addEventListener("click", cargarViajes);
document.getElementById("form-reserva").addEventListener("submit", crearReserva);
document.getElementById("ver-archivados").addEventListener("click", verArchivados);
document.getElementById("form-miembro").addEventListener("submit", agregarMiembro);
document.getElementById("novedades-itinerario").addEventListener("change", (evento) => {
  estado.itinerario = evento.target.value;
  cargarNovedades();
});
document.getElementById("form-agencia").addEventListener("submit", guardarAgencia);
document.getElementById("form-problema").addEventListener("submit", reportarProblema);
document.getElementById("form-remitente").addEventListener("submit", (evento) => {
  evento.preventDefault();
  aprobarRemitente(document.getElementById("remitente-seguro").value);
});
document.getElementById("quitar-remitente").addEventListener("click", quitarRemitente);
document.getElementById("form-correo").addEventListener("submit", autorizarCorreo);
document.getElementById("revocar-correo").addEventListener("click", revocarCorreo);
document.getElementById("form-asistente").addEventListener("submit", enviarTurno);
document.getElementById("form-cotizacion").addEventListener("submit", cotizar);
document.getElementById("volver-viajes").addEventListener("click", () => mostrar("viajes"));
document.getElementById("reintentar").addEventListener("click", () => {
  if (estado.repetir) estado.repetir();
});
for (const boton of document.querySelectorAll("#menu button[data-pantalla]")) {
  boton.addEventListener("click", () => mostrar(boton.dataset.pantalla));
}

if (sesion.token()) entrarCon(sesion.leer());
