"""Rutas principales de AgroSismo."""
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path
from django.views.generic import TemplateView

from accounts import views as cuentas

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", cuentas.landing, name="landing"),
    path("ingresar/", cuentas.IngresoView.as_view(), name="login"),
    path("salir/", LogoutView.as_view(), name="logout"),
    path("inicio/", cuentas.inicio, name="inicio"),
    path("ayuda/", cuentas.ayuda, name="ayuda"),
    path("manual/", cuentas.manual, name="manual"),
    path("recuperar/", cuentas.recuperar_clave, name="recuperar"),
    path("recuperar/enviada/", cuentas.recuperar_enviada, name="recuperar_enviada"),
    path("fincas/", cuentas.fincas_lista, name="fincas"),
    path("fincas/nueva/", cuentas.finca_crear, name="finca_crear"),
    path("fincas/<int:pk>/", cuentas.finca_detalle, name="finca_detalle"),
    path("fincas/<int:pk>/editar/", cuentas.finca_editar, name="finca_editar"),
    path("fincas/<int:pk>/estado/", cuentas.finca_estado, name="finca_estado"),
    path("fincas/<int:pk>/eliminar/", cuentas.finca_eliminar, name="finca_eliminar"),
    path("usuarios/solicitudes/<int:pk>/descartar/", cuentas.solicitud_descartar, name="solicitud_descartar"),
    path("usuarios/", cuentas.usuarios_lista, name="usuarios"),
    path("usuarios/nuevo/", cuentas.usuario_crear, name="usuario_crear"),
    path("usuarios/actividad/", cuentas.actividad_lista, name="actividad"),
    path("usuarios/<int:pk>/editar/", cuentas.usuario_editar, name="usuario_editar"),
    path("usuarios/<int:pk>/estado/", cuentas.usuario_estado, name="usuario_estado"),
    path("usuarios/<int:pk>/clave/", cuentas.usuario_clave, name="usuario_clave"),
    path("manifest.webmanifest", cuentas.manifest, name="manifest"),
    path("sw.js", cuentas.ServiceWorkerView.as_view(), name="sw"),
    path("sin-conexion/", TemplateView.as_view(template_name="pwa/sin_conexion.html"), name="sin_conexion"),
    path("", include("agro.urls")),
    path("", include("afectaciones.urls")),
]

# Las fotografías NO se publican en /media/: se entregan por una vista que verifica
# que quien las pide sea su propietario (afectaciones.views.evidencia_archivo).
