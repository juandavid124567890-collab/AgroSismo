/* Interacciones del panel de AgroSismo (sin librerías externas). */
(function () {
  "use strict";

  // 1) Números que suben hasta su valor.
  var reducir = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.querySelectorAll("[data-contar]").forEach(function (el) {
    var meta = parseInt(el.getAttribute("data-contar"), 10);
    if (isNaN(meta) || meta <= 0 || reducir) { return; }
    var inicio = null, dur = 700;
    function paso(t) {
      if (inicio === null) { inicio = t; }
      var p = Math.min((t - inicio) / dur, 1);
      el.textContent = Math.round(meta * (1 - Math.pow(1 - p, 3))).toLocaleString("es-CO");
      if (p < 1) { requestAnimationFrame(paso); }
    }
    el.textContent = "0";
    requestAnimationFrame(paso);
  });

  // 2) Mensajes: se cierran solos o con la X.
  document.querySelectorAll(".mensaje").forEach(function (m) {
    function cerrar() {
      m.classList.add("saliendo");
      setTimeout(function () { m.remove(); }, 250);
    }
    var x = m.querySelector(".cerrar");
    if (x) { x.addEventListener("click", cerrar); }
    if (m.classList.contains("clave")) {
      // Contraseña mostrada una sola vez: no se cierra sola y se puede copiar.
      var t = m.querySelector("span"), mt = t && t.textContent.match(/:\s(\S+)\s—/);
      if (mt && navigator.clipboard) {
        var c = document.createElement("button");
        c.type = "button"; c.className = "copiar"; c.textContent = "Copiar";
        c.addEventListener("click", function () {
          navigator.clipboard.writeText(mt[1]).then(function () { c.textContent = "Copiada ✓"; });
        });
        m.insertBefore(c, m.querySelector(".cerrar"));
      }
    } else if (!m.classList.contains("error")) { setTimeout(cerrar, 6000); }
  });

  // 3) Buscador en vivo para listas: <input data-filtrar="#lista"> y elementos con data-buscar.
  document.querySelectorAll("[data-filtrar]").forEach(function (campo) {
    var lista = document.querySelector(campo.getAttribute("data-filtrar"));
    if (!lista) { return; }
    var vacio = document.querySelector(campo.getAttribute("data-vacio") || "#sin-resultados");
    var cuenta = document.querySelector(campo.getAttribute("data-cuenta") || "#cuenta");
    function normalizar(t) {
      return (t || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    }
    function filtrar() {
      var q = normalizar(campo.value.trim());
      var visibles = 0;
      lista.querySelectorAll("[data-buscar]").forEach(function (it) {
        var ok = !q || normalizar(it.getAttribute("data-buscar")).indexOf(q) !== -1;
        it.hidden = !ok;
        if (ok) { visibles += 1; }
      });
      if (vacio) { vacio.hidden = visibles !== 0; }
      if (cuenta) { cuenta.textContent = visibles; }
    }
    campo.addEventListener("input", filtrar);
    var form = campo.closest("form");
    if (form) { form.addEventListener("submit", function (e) { e.preventDefault(); filtrar(); }); }
    filtrar();
  });

  // 4) Chips de severidad: eligen el filtro y lo aplican.
  document.querySelectorAll("[data-sev]").forEach(function (chip) {
    chip.addEventListener("click", function (e) {
      var form = document.querySelector("form.filtros");
      var sel = form && form.querySelector("select[name=severidad]");
      if (!sel) { return; }
      e.preventDefault();
      sel.value = chip.getAttribute("data-sev");
      form.submit();
    });
  });

  // 5) Botones con estado "cargando" (evita doble clic).
  document.querySelectorAll("form[data-cargando]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var b = form.querySelector("button[type=submit]");
      if (!b || b.disabled) { return; }
      var texto = b.innerHTML;
      b.disabled = true;
      b.classList.add("cargando");
      b.textContent = form.getAttribute("data-cargando");
      // El PDF se descarga sin recargar la página: se reactiva el botón.
      setTimeout(function () { b.disabled = false; b.classList.remove("cargando"); b.innerHTML = texto; }, 4000);
    });
  });

  // 6) Confirmación antes de acciones que borran.
  document.querySelectorAll("form[data-confirmar]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.getAttribute("data-confirmar"))) { e.preventDefault(); }
    });
  });

  // 7) Tarjetas completas clicables (sin perder el enlace principal).
  document.querySelectorAll("[data-ir]").forEach(function (el) {
    el.addEventListener("click", function (e) {
      if (e.target.closest("a, button, form")) { return; }
      window.location.href = el.getAttribute("data-ir");
    });
  });
  // 8) Teclado numérico en el celular para campos de número.
  document.querySelectorAll("input[type=number]").forEach(function (i) {
    if (!i.hasAttribute("inputmode")) { i.setAttribute("inputmode", "decimal"); }
  });

  // 9) Vista previa de la foto elegida antes de guardarla.
  document.querySelectorAll("input[type=file][accept^='image']").forEach(function (input) {
    input.addEventListener("change", function () {
      var prev = input.parentNode.querySelector(".vista-foto");
      if (prev) { prev.remove(); }
      var f = input.files && input.files[0];
      if (!f || !window.URL) { return; }
      var img = document.createElement("img");
      img.className = "vista-foto"; img.alt = "Vista previa de la fotografía";
      img.src = URL.createObjectURL(f);
      input.insertAdjacentElement("afterend", img);
    });
  });
})();
