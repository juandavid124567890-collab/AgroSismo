/* Medidor de contraseña: muestra requisitos y nivel Débil / Media / Fuerte. */
(function () {
  function nivel(c) {
    var clases = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter(function (r) { return r.test(c); }).length;
    if (c.length >= 10 && clases >= 3) return "fuerte";
    if (c.length >= 8 && clases >= 2) return "media";
    return "debil";
  }
  var TEXTO = { debil: "Débil", media: "Media", fuerte: "Fuerte" };
  var REGLAS = [
    ["Al menos 8 caracteres", function (c) { return c.length >= 8; }],
    ["Letras mayúsculas y minúsculas", function (c) { return /[a-z]/.test(c) && /[A-Z]/.test(c); }],
    ["Al menos un número", function (c) { return /[0-9]/.test(c); }],
    ["Al menos un símbolo (por ejemplo ! # $ % - _)", function (c) { return /[^A-Za-z0-9]/.test(c); }]
  ];
  document.querySelectorAll("[data-medidor-clave]").forEach(function (campo) {
    var caja = document.createElement("div");
    caja.className = "medidor-clave";
    caja.setAttribute("aria-live", "polite");
    caja.innerHTML =
      '<div class="medidor-barra"><span></span></div>' +
      '<p class="medidor-nivel"></p><ul class="medidor-reglas"></ul>' +
      '<p class="medidor-nota">Evita tu nombre, tu usuario, números seguidos (12345678) y claves comunes (como «password»).</p>';
    campo.insertAdjacentElement("afterend", caja);
    var ul = caja.querySelector("ul"), niv = caja.querySelector(".medidor-nivel");
    REGLAS.forEach(function (r) { var li = document.createElement("li"); li.textContent = r[0]; ul.appendChild(li); });
    function actualizar() {
      var c = campo.value;
      if (!c) { caja.dataset.nivel = ""; niv.textContent = "Opcional: si la dejas vacía, AgroSismo genera una segura."; }
      else { var n = nivel(c); caja.dataset.nivel = n; niv.innerHTML = 'Seguridad: <strong>' + TEXTO[n] + '</strong>'; }
      ul.querySelectorAll("li").forEach(function (li, i) { li.classList.toggle("ok", !!c && REGLAS[i][1](c)); });
    }
    campo.addEventListener("input", actualizar);
    actualizar();
  });
})();
