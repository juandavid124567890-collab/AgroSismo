from django.test import TestCase
from django.urls import resolve, reverse


class ManifestAtajosTests(TestCase):
    def test_el_manifest_tiene_id_iconos_y_atajos(self):
        datos = self.client.get(reverse("manifest")).json()
        self.assertEqual(datos["id"], "/inicio/")
        propositos = [i.get("purpose") for i in datos["icons"]]
        self.assertIn("maskable", propositos)
        self.assertEqual(len(datos["shortcuts"]), 2)

    def test_los_atajos_apuntan_a_paginas_que_existen(self):
        datos = self.client.get(reverse("manifest")).json()
        for atajo in datos["shortcuts"]:
            self.assertTrue(resolve(atajo["url"]))

    def test_la_pagina_declara_la_app_para_iphone(self):
        r = self.client.get(reverse("login"))
        self.assertContains(r, "apple-mobile-web-app-title")
        self.assertContains(r, "apple-touch-icon")
