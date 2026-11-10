/* Carrusel de pantallas de ejemplo de la página pública. */
(function () {
  var visor = document.querySelector(".pub-visor");
  if (!visor) return;
  var diapos = Array.prototype.slice.call(visor.querySelectorAll(".pub-diapo"));
  var pista = visor.querySelector(".pub-pista");
  var progreso = visor.querySelector(".pub-progreso");
  var leyenda = visor.querySelector(".pub-visor-leyenda");
  var puntos = visor.querySelector(".pub-visor-puntos");
  var actual = 0, reloj = null;
  var reducido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  diapos.forEach(function (d, i) {
    var b = document.createElement("button");
    b.type = "button";
    b.setAttribute("aria-label", "Ver pantalla " + (i + 1) + " de " + diapos.length);
    b.addEventListener("click", function () { ir(i); reiniciar(); });
    puntos.appendChild(b);
  });
  var botones = puntos.querySelectorAll("button");

  function ir(n) {
    actual = (n + diapos.length) % diapos.length;
    pista.style.transform = "translateX(-" + (actual * 100) + "%)";
    botones.forEach(function (b, i) { b.classList.toggle("activo", i === actual); b.setAttribute("aria-current", i === actual ? "true" : "false"); });
    leyenda.textContent = diapos[actual].getAttribute("data-leyenda") || "";
  }
  function iniciar() {
    if (reducido || reloj) return;
    reloj = setInterval(function () { ir(actual + 1); barra(); }, 4500);
    barra();
  }
  function barra() {
    progreso.classList.remove("corre"); void progreso.offsetWidth; progreso.classList.add("corre");
  }
  function parar() { clearInterval(reloj); reloj = null; progreso.classList.remove("corre"); }
  function reiniciar() { parar(); iniciar(); }

  visor.querySelectorAll(".pub-visor-flecha").forEach(function (f) {
    f.addEventListener("click", function () { ir(actual + Number(f.getAttribute("data-dir"))); reiniciar(); });
  });
  visor.addEventListener("mouseenter", parar);
  visor.addEventListener("mouseleave", iniciar);
  visor.addEventListener("focusin", parar);
  visor.addEventListener("focusout", iniciar);
  document.addEventListener("visibilitychange", function () { document.hidden ? parar() : iniciar(); });

  var x0 = null;
  visor.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; }, { passive: true });
  visor.addEventListener("touchend", function (e) {
    if (x0 === null) return;
    var dx = e.changedTouches[0].clientX - x0; x0 = null;
    if (Math.abs(dx) > 40) { ir(actual + (dx < 0 ? 1 : -1)); reiniciar(); }
  }, { passive: true });

  ir(0); iniciar();
})();
