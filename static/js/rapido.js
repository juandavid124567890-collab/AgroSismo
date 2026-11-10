/* Pantalla "Registro rápido": guarda sismos y afectaciones en el dispositivo. */
(function () {
  "use strict";
  var A = window.AgroOffline;
  var $ = function (id) { return document.getElementById(id); };
  var base = null;          // fincas y catálogos del usuario
  var eventoActual = null;  // sismo al que se están agregando afectaciones

  function el(tag, clase, texto) {
    var e = document.createElement(tag);
    if (clase) { e.className = clase; }
    if (texto !== undefined) { e.textContent = texto; }
    return e;
  }
  function opciones(select, pares, vacio) {
    select.innerHTML = "";
    if (vacio) { var o = el("option", "", vacio); o.value = ""; select.appendChild(o); }
    pares.forEach(function (p) { var o = el("option", "", p[1]); o.value = p[0]; select.appendChild(o); });
  }
  function formatoFecha(iso) {
    var d = new Date(iso);
    return d.toLocaleString("es-CO", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
  }
  function ahoraLocal() {
    var d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
  }
  function unidadSel() {
    var id = $("unidad").value;
    return (base.unidades || []).filter(function (u) { return u.id === id; })[0] || null;
  }

  // ---- Fotografías elegidas (se guardan en el dispositivo y se suben al sincronizar) ----
  var MAX_FOTOS = 10;
  var fotosElegidas = [];

  function comprimir(archivo) {
    // Reduce la foto (máx. 1600 px, JPEG) para ahorrar espacio y datos móviles.
    return new Promise(function (ok) {
      if (!window.createImageBitmap) { ok({ blob: archivo, nombre: archivo.name }); return; }
      createImageBitmap(archivo).then(function (bmp) {
        var esc = Math.min(1, 1600 / Math.max(bmp.width, bmp.height));
        var c = document.createElement("canvas");
        c.width = Math.round(bmp.width * esc); c.height = Math.round(bmp.height * esc);
        c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
        if (bmp.close) { bmp.close(); }
        c.toBlob(function (b) {
          if (b && b.size < archivo.size) { ok({ blob: b, nombre: "foto.jpg" }); }
          else { ok({ blob: archivo, nombre: archivo.name }); }
        }, "image/jpeg", 0.8);
      }).catch(function () { ok({ blob: archivo, nombre: archivo.name }); });
    });
  }

  function pintarFotosElegidas() {
    var cont = $("vista-fotos");
    cont.innerHTML = "";
    fotosElegidas.forEach(function (f, i) {
      var caja = el("div", "miniatura");
      var img = el("img"); img.alt = "Fotografía " + (i + 1); img.src = URL.createObjectURL(f);
      img.addEventListener("load", function () { URL.revokeObjectURL(img.src); });
      var x = el("button", "quitar-miniatura", "×"); x.type = "button"; x.setAttribute("aria-label", "Quitar fotografía " + (i + 1));
      x.addEventListener("click", function () { fotosElegidas.splice(i, 1); pintarFotosElegidas(); });
      caja.appendChild(img); caja.appendChild(x); cont.appendChild(caja);
    });
    $("cuenta-fotos").textContent = fotosElegidas.length + " de " + MAX_FOTOS;
  }

  function elegirFotos(lista) {
    var avisos = [];
    Array.prototype.forEach.call(lista, function (f) {
      if (!/^image\//.test(f.type)) { avisos.push("«" + f.name + "» no es una imagen."); return; }
      if (fotosElegidas.length >= MAX_FOTOS) { avisos.push("Solo se pueden adjuntar " + MAX_FOTOS + " fotografías por daño."); return; }
      fotosElegidas.push(f);
    });
    $("fotos").value = "";
    pintarFotosElegidas();
    mostrarErrores(avisos.filter(function (x, i) { return avisos.indexOf(x) === i; }));
  }

  function estadoRed() {
    var en = navigator.onLine;
    var chip = $("estado-red");
    chip.textContent = en ? "Con conexión" : "Sin conexión";
    chip.className = "estado-red " + (en ? "on" : "off");
    $("aviso-red").textContent = en
      ? "Con conexión: tus registros se guardan en este dispositivo y se envían al servidor automáticamente."
      : "Sin conexión: tus registros se guardan en este dispositivo y se enviarán solos cuando vuelva el internet.";
  }

  function mostrarErrores(lista) {
    var caja = $("errores");
    caja.innerHTML = "";
    caja.hidden = lista.length === 0;
    lista.forEach(function (t) { caja.appendChild(el("div", "", t)); });
    if (lista.length) { caja.scrollIntoView({ behavior: "smooth", block: "center" }); }
  }

  function cargarCultivos() {
    var u = unidadSel();
    var lista = u ? u.cultivos.map(function (c) { return [c.id, c.tipo]; }) : [];
    opciones($("cultivo"), lista, "— Ninguno en particular —");
  }

  function fijarEvento(ev) {
    eventoActual = ev;
    var bloqueado = !!ev;
    ["unidad", "fecha", "magnitud", "epicentro"].forEach(function (id) { $(id).disabled = bloqueado; });
    $("bloque-evento-fijo").hidden = !bloqueado;
    if (ev) { $("evento-fijo-texto").textContent = ev.finca + " · " + formatoFecha(ev.fecha); }
  }

  function validar() {
    var errores = [];
    var u = unidadSel();
    if (!u) { errores.push("Elige la unidad agrícola."); }
    if (!eventoActual) {
      var f = $("fecha").value;
      if (!f) { errores.push("Indica la fecha y hora del sismo."); }
      else if (new Date(f) > new Date()) { errores.push("La fecha del sismo no puede estar en el futuro."); }
      var m = $("magnitud").value;
      if (m !== "" && (isNaN(m) || +m < 0 || +m > 10)) { errores.push("La magnitud debe estar entre 0 y 10."); }
    }
    var sev = document.querySelector("input[name=severidad]:checked");
    if (!sev) { errores.push("Elige el nivel de severidad."); }
    if (!$("elemento").value) { errores.push("Elige el elemento afectado."); }
    if (!$("tipo_dano").value) { errores.push("Elige el tipo de daño."); }
    else if ($("tipo_dano").value === "OTRO" && !$("tipo_dano_otro").value.trim()) { errores.push("Escribe cuál es el otro daño."); }
    var area = $("area").value;
    if (area === "" || isNaN(area) || +area < 0) { errores.push("Indica el área afectada (0 o más hectáreas)."); }
    else if (u && +area > +u.area_ha) { errores.push("El área afectada supera el área de la unidad (" + u.area_ha + " ha)."); }
    var cant = $("perdida_cantidad").value, val = $("perdida_valor").value;
    if ((cant !== "" && (isNaN(cant) || +cant < 0)) || (val !== "" && (isNaN(val) || +val < 0))) {
      errores.push("La pérdida debe ser un número positivo.");
    }
    return errores;
  }

  function guardar(otra) {
    var errores = validar();
    mostrarErrores(errores);
    if (errores.length) { return Promise.resolve(false); }
    var u = unidadSel();
    var ahora = new Date().toISOString();
    var elegidas = fotosElegidas.slice();
    return Promise.all(elegidas.map(comprimir)).then(function (fotos) {
      var trabajos = [];
      if (!eventoActual) {
        var evento = {
          id: A.uuid(), unidad_id: u.id, fecha_hora: new Date($("fecha").value).toISOString(),
          magnitud: $("magnitud").value, epicentro: $("epicentro").value.trim(), creado_en: ahora
        };
        eventoActual = { id: evento.id, unidad_id: u.id, finca: u.nombre, fecha: evento.fecha_hora };
        trabajos.push(A.guardar({
          id: evento.id, tipo: "evento", usuario: base.usuario_id, estado: "pendiente",
          creado: ahora, payload: evento, resumen: { finca: u.nombre, fecha: evento.fecha_hora, magnitud: evento.magnitud }
        }));
      }
      var sev = document.querySelector("input[name=severidad]:checked").value;
      var af = {
        id: A.uuid(), evento_id: eventoActual.id, cultivo_id: $("cultivo").value || null,
        elemento: $("elemento").value, tipo_dano: $("tipo_dano").value, tipo_dano_otro: $("tipo_dano_otro").value.trim(), severidad: sev,
        area_afectada_ha: $("area").value, observaciones: $("observaciones").value.trim(), creado_en: ahora,
        perdida: {
          cantidad: $("perdida_cantidad").value || "0", unidad_medida: $("perdida_unidad").value,
          valor_estimado_cop: $("perdida_valor").value || "0"
        }
      };
      trabajos.push(A.guardar({
        id: af.id, tipo: "afectacion", usuario: base.usuario_id, estado: "pendiente", creado: ahora, payload: af,
        resumen: { dano: ($("tipo_dano").value === "OTRO" && af.tipo_dano_otro) ? "Otro: " + af.tipo_dano_otro : $("tipo_dano").selectedOptions[0].textContent, severidad: sev, area: af.area_afectada_ha }
      }));
      fotos.forEach(function (f) {
        var id = A.uuid();
        trabajos.push(A.guardar({
          id: id, tipo: "foto", usuario: base.usuario_id, estado: "pendiente", creado: ahora,
          payload: { id: id, afectacion_id: af.id, descripcion: "", creado_en: ahora },
          blob: f.blob, nombre: f.nombre, resumen: {}
        }));
      });
      return Promise.all(trabajos);
    }).then(function () {
      limpiarAfectacion();
      if (otra) { fijarEvento(eventoActual); }
      else { fijarEvento(null); limpiarEvento(); }
      aviso("Guardado en este dispositivo.");
      return pintarLista();
    }).then(function () { sincronizar(); return true; })
      .catch(function () {
        mostrarErrores(["No se pudo guardar en este dispositivo (¿poco espacio?). Intenta con menos fotos."]);
        return false;
      });
  }

  function limpiarAfectacion() {
    ["area", "observaciones", "perdida_cantidad", "perdida_valor"].forEach(function (id) { $(id).value = ""; });
    document.querySelectorAll("input[name=severidad]").forEach(function (r) { r.checked = false; });
    $("elemento").value = ""; $("tipo_dano").value = ""; $("cultivo").value = "";
    $("tipo_dano").dispatchEvent(new Event("change"));
    $("perdida_valor").dispatchEvent(new Event("input"));
    fotosElegidas = []; pintarFotosElegidas();
  }
  function limpiarEvento() {
    $("fecha").value = ahoraLocal(); $("magnitud").value = ""; $("epicentro").value = "";
  }
  function aviso(texto) {
    var a = $("aviso-ok");
    a.textContent = texto; a.hidden = false;
    clearTimeout(aviso.t);
    aviso.t = setTimeout(function () { a.hidden = true; }, 4000);
  }

  var CHIP = {
    pendiente: ["chip est-pendiente", "Pendiente"],
    sincronizado: ["chip est-ok", "Sincronizado"],
    error: ["chip est-error", "Con error"]
  };
  function chipEstado(estado) {
    var c = CHIP[estado] || CHIP.pendiente;
    return el("span", c[0], c[1]);
  }

  function pintarLista() {
    return A.deUsuario(base.usuario_id).then(function (items) {
      var cont = $("pendientes");
      cont.innerHTML = "";
      var porEnviar = items.filter(function (i) { return i.estado !== "sincronizado"; }).length;
      var listos = items.filter(function (i) { return i.estado === "sincronizado"; }).length;
      $("cuenta-pendientes").textContent = porEnviar;
      $("sin-pendientes").hidden = items.length !== 0;
      $("btn-sync").disabled = porEnviar === 0 || !navigator.onLine || sincronizando;
      $("btn-limpiar").hidden = listos === 0;
      var eventos = items.filter(function (i) { return i.tipo === "evento"; })
        .sort(function (a, b) { return a.creado < b.creado ? 1 : -1; });
      var afect = items.filter(function (i) { return i.tipo === "afectacion"; });
      var fotosDe = function (afId) { return items.filter(function (i) { return i.tipo === "foto" && i.payload.afectacion_id === afId; }); };
      eventos.forEach(function (ev) {
        var propias = afect.filter(function (a) { return a.payload.evento_id === ev.id; });
        var tarjeta = el("div", "pend");
        var cab = el("div", "pend-cab");
        var t = el("div");
        t.appendChild(el("strong", "", formatoFecha(ev.payload.fecha_hora) + (ev.resumen.magnitud ? " · " + ev.resumen.magnitud + " ML" : "")));
        t.appendChild(el("div", "suave", ev.resumen.finca));
        cab.appendChild(t);
        cab.appendChild(chipEstado(ev.estado));
        tarjeta.appendChild(cab);
        if (ev.nota) { tarjeta.appendChild(el("div", "pend-nota", ev.nota)); }
        if (ev.error) { tarjeta.appendChild(el("div", "pend-error", ev.error)); }
        propias.forEach(function (a) {
          var fila = el("div", "pend-fila");
          var izq = el("div");
          var txt = el("span", "", a.resumen.dano + " · " + a.resumen.area + " ha ");
          txt.appendChild(el("span", "sev sev-" + a.resumen.severidad.toLowerCase(), a.resumen.severidad.charAt(0) + a.resumen.severidad.slice(1).toLowerCase()));
          izq.appendChild(txt);
          if (a.error) { izq.appendChild(el("div", "pend-error", a.error)); }
          var fs = fotosDe(a.id);
          if (fs.length) {
            var tira = el("div", "pend-fotos");
            fs.forEach(function (f) {
              var m = el("div", "mini " + f.estado);
              if (f.blob) {
                var im = el("img"); im.alt = "Fotografía"; im.src = URL.createObjectURL(f.blob);
                im.addEventListener("load", function () { URL.revokeObjectURL(im.src); });
                m.appendChild(im);
              } else { m.appendChild(el("span", "", "✓")); }
              m.title = f.estado === "sincronizado" ? "Foto enviada" : (f.estado === "error" ? f.error : "Foto pendiente de enviar");
              if (f.estado !== "sincronizado") {
                var qf = el("button", "quitar-miniatura", "×"); qf.type = "button"; qf.setAttribute("aria-label", "Quitar fotografía");
                qf.addEventListener("click", function () { quitar([f.id]); });
                m.appendChild(qf);
              }
              tira.appendChild(m);
            });
            izq.appendChild(tira);
            fs.filter(function (f) { return f.error; }).forEach(function (f) { izq.appendChild(el("div", "pend-error", "Foto: " + f.error)); });
          }
          fila.appendChild(izq);
          var der = el("div", "pend-der");
          der.appendChild(chipEstado(a.estado));
          if (a.estado !== "sincronizado") {
            var q = el("button", "enlace-boton", "Quitar"); q.type = "button";
            q.addEventListener("click", function () { quitar([a.id].concat(fotosDe(a.id).map(function (f) { return f.id; }))); });
            der.appendChild(q);
          }
          fila.appendChild(der);
          tarjeta.appendChild(fila);
        });
        var sincro = ev.estado === "sincronizado" && propias.every(function (a) {
          return a.estado === "sincronizado" && fotosDe(a.id).every(function (f) { return f.estado === "sincronizado"; });
        });
        if (!sincro) {
          var qe = el("button", "enlace-boton", "Quitar sismo y sus daños"); qe.type = "button";
          qe.addEventListener("click", function () {
            if (!window.confirm("¿Quitar este sismo y todos sus daños de este dispositivo?")) { return; }
            var ids = [];
            propias.forEach(function (a) { ids.push(a.id); fotosDe(a.id).forEach(function (f) { ids.push(f.id); }); });
            ids.push(ev.id);
            if (eventoActual && eventoActual.id === ev.id) { fijarEvento(null); limpiarEvento(); }
            quitar(ids);
          });
          tarjeta.appendChild(qe);
        }
        cont.appendChild(tarjeta);
      });
    });
  }
  function quitar(ids) {
    return Promise.all(ids.map(function (id) { return A.quitar(id); })).then(pintarLista);
  }

  // ---- Envío al servidor ----
  var sincronizando = false;
  function cookie(nombre) {
    var m = document.cookie.match(new RegExp("(?:^|; )" + nombre + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : "";
  }
  function mensajeSync(texto, tipo) {
    var m = $("msg-sync");
    m.textContent = texto; m.className = "msg-sync " + (tipo || ""); m.hidden = !texto;
  }
  function textoErrores(e) {
    if (!e) { return "No se pudo guardar."; }
    return Object.keys(e).map(function (k) { return e[k]; }).join(" ");
  }

  function sincronizar() {
    if (sincronizando || !navigator.onLine || !base) { return Promise.resolve(); }
    sincronizando = true;
    $("btn-sync").disabled = true;
    return A.deUsuario(base.usuario_id).then(function (items) {
      var enviar = items.filter(function (i) { return i.estado !== "sincronizado" && i.tipo !== "foto"; });
      if (!enviar.length) { mensajeSync(""); return subirFotos(); }
      // Sismos que ya se unieron a otro existente: usar el identificador del servidor.
      var mapa = {};
      items.forEach(function (i) { if (i.tipo === "evento" && i.id_servidor) { mapa[i.id] = i.id_servidor; } });
      var lote = {
        eventos: enviar.filter(function (i) { return i.tipo === "evento"; }).map(function (i) { return i.payload; }),
        afectaciones: enviar.filter(function (i) { return i.tipo === "afectacion"; }).map(function (i) {
          var p = Object.assign({}, i.payload);
          if (mapa[p.evento_id]) { p.evento_id = mapa[p.evento_id]; }
          return p;
        })
      };
      mensajeSync("Enviando " + enviar.length + " registro(s)…", "");
      var enviarLote = function () {
        return fetch("/api/sincronizar/", {
          method: "POST", credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") },
          body: JSON.stringify(lote)
        });
      };
      var preparar = cookie("csrftoken") ? Promise.resolve() : A.refrescarBase();
      return preparar.then(enviarLote).then(function (r) {
        if (r.status === 401) { mensajeSync("Tu sesión terminó. Inicia sesión con internet para enviar tus registros.", "error"); return; }
        if (!r.ok) { mensajeSync("El servidor no pudo recibir el lote (código " + r.status + "). Se intentará de nuevo.", "error"); return; }
        return r.json().then(function (datos) { return aplicarResultados(enviar, datos.resultados); }).then(subirFotos);
      });
    }).catch(function () {
      mensajeSync("No hay conexión con el servidor. Tus registros siguen guardados y se enviarán después.", "aviso");
    }).then(function () {
      sincronizando = false;
      return pintarLista();
    });
  }

  function subirFotos() {
    return A.deUsuario(base.usuario_id).then(function (items) {
      var listas = {};
      items.forEach(function (i) { if (i.tipo === "afectacion" && i.estado === "sincronizado") { listas[i.id] = true; } });
      var cola = items.filter(function (i) {
        return i.tipo === "foto" && i.estado === "pendiente" && i.blob && listas[i.payload.afectacion_id];
      });
      if (!cola.length) { return; }
      var ok = 0, fallos = 0;
      return cola.reduce(function (prev, it) {
        return prev.then(function (parar) {
          if (parar) { return true; }
          var fd = new FormData();
          fd.append("id", it.payload.id); fd.append("afectacion_id", it.payload.afectacion_id);
          fd.append("descripcion", it.payload.descripcion || ""); fd.append("creado_en", it.payload.creado_en);
          fd.append("imagen", it.blob, it.nombre || "foto.jpg");
          return fetch("/api/fotos/", { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": cookie("csrftoken") }, body: fd })
            .then(function (r) {
              if (!r.ok) { return true; } // sesión vencida o servidor ocupado: se reintenta después
              return r.json().then(function (res) {
                if (res.estado === "ok" || res.estado === "ya_existia") { it.estado = "sincronizado"; it.blob = null; it.error = ""; ok += 1; }
                else { it.estado = "error"; it.error = textoErrores(res.errores); fallos += 1; }
                return A.guardar(it).then(function () { return false; });
              });
            });
        });
      }, Promise.resolve(false)).then(function () {
        if (!ok && !fallos) { return; }
        var m = $("msg-sync"), previo = m.hidden ? "" : m.textContent + " ";
        mensajeSync(previo + ok + " foto(s) enviada(s)" + (fallos ? ", " + fallos + " con error." : "."), fallos ? "error" : "ok");
      });
    });
  }

  function aplicarResultados(enviados, res) {
    var porId = {};
    ["eventos", "afectaciones"].forEach(function (k) { (res[k] || []).forEach(function (x) { porId[x.id] = x; }); });
    var ok = 0, fallos = 0, trabajos = [];
    enviados.forEach(function (it) {
      var r = porId[it.payload.id];
      if (!r) { return; }
      if (r.estado === "ok" || r.estado === "ya_existia") {
        it.estado = "sincronizado"; it.error = ""; it.sincronizado = new Date().toISOString(); ok += 1;
      } else if (r.estado === "conflicto") {
        it.estado = "sincronizado"; it.error = ""; it.id_servidor = r.id_existente;
        it.nota = "Ya tenías un sismo registrado en esa unidad y fecha; tus daños se unieron a él."; ok += 1;
      } else {
        it.estado = "error"; it.error = textoErrores(r.errores); fallos += 1;
      }
      trabajos.push(A.guardar(it));
    });
    return Promise.all(trabajos).then(function () {
      if (fallos) { mensajeSync(ok + " enviado(s). " + fallos + " tiene(n) un error: revísalos abajo y quítalos o corrígelos.", "error"); }
      else { mensajeSync("Listo: " + ok + " registro(s) sincronizado(s).", "ok"); }
      return A.refrescarBase();
    });
  }

  function iniciar() {
    estadoRed();
    window.addEventListener("online", function () { estadoRed(); sincronizar(); });
    window.addEventListener("offline", function () { estadoRed(); if (base) { pintarLista(); } });

    A.refrescarBase().then(function () { return A.leerBase(); }).then(function (b) {
      if (!b || !b.unidades || !b.unidades.length) {
        $("sin-base").hidden = false;
        $("sin-base-texto").textContent = b
          ? "Todavía no tienes unidades agrícolas registradas. Crea una con internet y vuelve aquí."
          : "Abre AgroSismo con internet e inicia sesión una vez para descargar tus unidades a este dispositivo.";
        return;
      }
      base = b;
      var cat = base.catalogos;
      opciones($("unidad"), base.unidades.map(function (u) { return [u.id, u.nombre]; }));
      opciones($("elemento"), cat.elementos, "— Elige —");
      opciones($("tipo_dano"), cat.tipos_dano, "— Elige —");
      opciones($("perdida_unidad"), cat.unidades_medida);
      cargarCultivos();
      $("unidad").addEventListener("change", cargarCultivos);
      limpiarEvento();
      $("formulario").hidden = false;
      $("formulario").addEventListener("submit", function (e) { e.preventDefault(); guardar(false); });
      $("btn-otra").addEventListener("click", function () { guardar(true); });
      $("btn-nuevo-sismo").addEventListener("click", function () { fijarEvento(null); limpiarEvento(); });
      $("lista").hidden = false;
      $("btn-sync").addEventListener("click", sincronizar);
      $("btn-limpiar").addEventListener("click", function () {
        A.deUsuario(base.usuario_id).then(function (items) {
          // Se conservan los registros enviados que aún necesitan reintentar algo pendiente.
          var bloqAf = {}, bloqEv = {};
          items.forEach(function (i) { if (i.tipo === "foto" && i.estado !== "sincronizado") { bloqAf[i.payload.afectacion_id] = true; } });
          items.forEach(function (i) {
            if (i.tipo === "afectacion" && (i.estado !== "sincronizado" || bloqAf[i.id])) { bloqEv[i.payload.evento_id] = true; }
          });
          return quitar(items.filter(function (i) {
            if (i.estado !== "sincronizado") { return false; }
            if (i.tipo === "afectacion") { return !bloqAf[i.id]; }
            if (i.tipo === "evento") { return !bloqEv[i.id]; }
            return true;
          }).map(function (i) { return i.id; }));
        });
      });
      $("fotos").addEventListener("change", function () { elegirFotos(this.files); });
      pintarFotosElegidas();
      return pintarLista().then(sincronizar);
    }).catch(function (e) {
      $("sin-base").hidden = false;
      $("sin-base-texto").textContent = "No se pudo usar el almacenamiento del dispositivo: " + e.message;
    });
  }
  iniciar();
})();
