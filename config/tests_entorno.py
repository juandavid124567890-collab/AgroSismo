import os
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from .entorno import cargar_env


class CargarEnvTests(SimpleTestCase):
    def _archivo(self, texto):
        d = tempfile.mkdtemp()
        ruta = Path(d) / ".env"
        ruta.write_text(texto, encoding="utf-8")
        return ruta

    def setUp(self):
        self._antes = dict(os.environ)
        for k in ("PRUEBA_A", "PRUEBA_B", "PRUEBA_C", "PRUEBA_D", "PRUEBA_E"):
            os.environ.pop(k, None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._antes)

    def test_lee_valores_con_y_sin_comillas_y_comentarios(self):
        ruta = self._archivo("# nota\n\nPRUEBA_A=hola\nPRUEBA_B='con espacios y @'\nPRUEBA_C=\"x\"\n")
        cargar_env(ruta)
        self.assertEqual(os.environ["PRUEBA_A"], "hola")
        self.assertEqual(os.environ["PRUEBA_B"], "con espacios y @")
        self.assertEqual(os.environ["PRUEBA_C"], "x")

    def test_no_pisa_lo_que_ya_esta_en_la_terminal(self):
        os.environ["PRUEBA_A"] = "terminal"
        cargar_env(self._archivo("PRUEBA_A=archivo\n"))
        self.assertEqual(os.environ["PRUEBA_A"], "terminal")

    def test_tolera_el_formato_de_powershell(self):
        cargar_env(self._archivo("$env:PRUEBA_D='agrosismo'\nexport PRUEBA_E=1\n"))
        self.assertEqual(os.environ["PRUEBA_D"], "agrosismo")
        self.assertEqual(os.environ["PRUEBA_E"], "1")

    def test_archivo_inexistente_no_falla(self):
        self.assertEqual(cargar_env("/no/existe/.env"), [])
