/* Almacenamiento en el dispositivo (IndexedDB) para el registro sin conexión.
   - "meta": guarda las fincas y catálogos descargados (se refresca con internet).
   - "cola": registros creados sin conexión, pendientes de enviar al servidor. */
(function () {
  "use strict";
  var DB = "agrosismo", VERSION = 1;

  function abrir() {
    return new Promise(function (ok, fallo) {
      if (!window.indexedDB) { fallo(new Error("Este navegador no permite guardar sin conexión.")); return; }
      var r = indexedDB.open(DB, VERSION);
      r.onupgradeneeded = function () {
        var db = r.result;
        if (!db.objectStoreNames.contains("meta")) { db.createObjectStore("meta"); }
        if (!db.objectStoreNames.contains("cola")) { db.createObjectStore("cola", { keyPath: "id" }); }
      };
      r.onsuccess = function () { ok(r.result); };
      r.onerror = function () { fallo(r.error); };
    });
  }

  function operar(almacen, modo, fn) {
    return abrir().then(function (db) {
      return new Promise(function (ok, fallo) {
        var t = db.transaction(almacen, modo);
        var peticion = fn(t.objectStore(almacen));
        t.oncomplete = function () { db.close(); ok(peticion ? peticion.result : undefined); };
        t.onerror = t.onabort = function () { db.close(); fallo(t.error); };
      });
    });
  }

  function uuid() {
    if (window.crypto && crypto.randomUUID) { return crypto.randomUUID(); }
    var b = new Uint8Array(16);
    (window.crypto || window.msCrypto).getRandomValues(b);
    b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80;
    var h = Array.prototype.map.call(b, function (x) { return ("0" + x.toString(16)).slice(-2); }).join("");
    return h.slice(0, 8) + "-" + h.slice(8, 12) + "-" + h.slice(12, 16) + "-" + h.slice(16, 20) + "-" + h.slice(20);
  }

  var AgroOffline = {
    uuid: uuid,
    leerBase: function () { return operar("meta", "readonly", function (s) { return s.get("base"); }); },
    guardarBase: function (datos) { return operar("meta", "readwrite", function (s) { return s.put(datos, "base"); }); },
    borrarBase: function () { return operar("meta", "readwrite", function (s) { return s.delete("base"); }); },
    todos: function () { return operar("cola", "readonly", function (s) { return s.getAll(); }); },
    guardar: function (item) { return operar("cola", "readwrite", function (s) { return s.put(item); }); },
    quitar: function (id) { return operar("cola", "readwrite", function (s) { return s.delete(id); }); },
    // Registros pendientes que pertenecen al usuario indicado.
    deUsuario: function (usuarioId) {
      return AgroOffline.todos().then(function (lista) {
        return lista.filter(function (x) { return x.usuario === usuarioId; });
      });
    },
    // Descarga fincas y catálogos del usuario (solo si hay internet y sesión).
    refrescarBase: function () {
      if (!navigator.onLine) { return Promise.resolve(null); }
      return fetch("/api/datos-base/", { credentials: "same-origin", headers: { Accept: "application/json" } })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (datos) { return datos ? AgroOffline.guardarBase(datos).then(function () { return datos; }) : null; })
        .catch(function () { return null; });
    }
  };
  window.AgroOffline = AgroOffline;

  // Al cerrar sesión se borran las fincas guardadas en el dispositivo.
  document.querySelectorAll("form[action$='/salir/']").forEach(function (f) {
    f.addEventListener("submit", function () { AgroOffline.borrarBase().catch(function () {}); });
  });

  // En cada página con sesión, mantener actualizadas las fincas guardadas.
  if (document.body.classList.contains("app")) { AgroOffline.refrescarBase(); }
})();
