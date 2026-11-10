/* Departamento -> municipio: el segundo desplegable muestra solo los municipios del departamento elegido. */
(function () {
  var datos = document.getElementById("divipola-datos");
  var depto = document.getElementById("id_departamento");
  var mun = document.getElementById("id_municipio");
  if (!datos || !depto || !mun) return;
  var mapa;
  try { mapa = JSON.parse(datos.textContent); } catch (e) { return; }

  function opcion(valor, texto) {
    var o = document.createElement("option");
    o.value = valor; o.textContent = texto;
    return o;
  }
  function llenar(conservar) {
    var lista = mapa[depto.value] || [];
    var actual = conservar ? mun.value : "";
    mun.innerHTML = "";
    mun.appendChild(opcion("", lista.length ? "Selecciona un municipio" : "Primero elige el departamento"));
    lista.forEach(function (m) { mun.appendChild(opcion(m, m)); });
    if (actual && lista.indexOf(actual) !== -1) mun.value = actual;
  }
  depto.addEventListener("change", function () { llenar(false); });
  // Al cargar, el servidor ya dejó la lista correcta; solo se vuelve a armar si hace falta.
  if (depto.value && mun.options.length <= 1) llenar(true);
})();
