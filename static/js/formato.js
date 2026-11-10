/* Ayudas de formulario: "Otro: ¿cuál?" y valores con puntos de miles. */
(function () {
  "use strict";

  function miles(n) { return Math.round(n).toLocaleString("es-CO"); }

  // 1) Mostrar el cuadro de texto solo cuando el tipo de daño es "Otro".
  function conectarOtro() {
    var tipo = document.getElementById("tipo_dano") || document.getElementById("id_tipo_dano");
    var otro = document.getElementById("tipo_dano_otro") || document.getElementById("id_tipo_dano_otro");
    if (!tipo || !otro) { return; }
    var caja = otro.closest(".campo") || otro.parentNode;
    function actualizar() {
      var es = tipo.value === "OTRO";
      caja.hidden = !es;
      otro.required = es;
      if (!es) { otro.value = ""; }
    }
    tipo.addEventListener("change", actualizar);
    actualizar();
  }

  // 2) Debajo de cada campo de dinero, mostrar el valor con puntos (1.500.000).
  function conectarMiles() {
    document.querySelectorAll("input[data-miles]").forEach(function (campo) {
      var pista = document.createElement("small");
      pista.className = "suave ayuda miles-pista";
      pista.setAttribute("aria-live", "polite");
      campo.insertAdjacentElement("afterend", pista);
      function pintar() {
        var n = parseFloat(campo.value);
        pista.textContent = (isFinite(n) && n > 0) ? "= $" + miles(n) + " COP" : "";
      }
      campo.addEventListener("input", pintar);
      campo.addEventListener("change", pintar);
      pintar();
    });
  }

  conectarOtro();
  conectarMiles();
})();
