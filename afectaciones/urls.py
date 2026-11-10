from django.urls import path
from django.views.generic import TemplateView

from . import api, views

urlpatterns = [
    path("registro-rapido/", TemplateView.as_view(template_name="pwa/registro_rapido.html"), name="registro_rapido"),
    path("api/datos-base/", api.datos_base, name="api_datos_base"),
    path("api/fotos/", api.subir_foto, name="api_subir_foto"),
    path("api/sincronizar/", api.sincronizar, name="api_sincronizar"),
    path("historial/", views.historial, name="historial"),
    path("reportes/", views.reporte, name="reporte"),
    path("reportes/pdf/", views.reporte_pdf, name="reporte_pdf"),
    path("eventos/", views.eventos_lista, name="eventos"),
    path("eventos/nuevo/", views.evento_crear, name="evento_crear"),
    path("eventos/<uuid:pk>/", views.evento_detalle, name="evento_detalle"),
    path("eventos/<uuid:pk>/editar/", views.evento_editar, name="evento_editar"),
    path("eventos/<uuid:pk>/afectaciones/nueva/", views.afectacion_crear, name="afectacion_crear"),
    path("afectaciones/<uuid:pk>/", views.afectacion_detalle, name="afectacion_detalle"),
    path("afectaciones/<uuid:pk>/editar/", views.afectacion_editar, name="afectacion_editar"),
    path("afectaciones/<uuid:pk>/fotos/nueva/", views.evidencia_agregar, name="evidencia_agregar"),
    path("fotos/<uuid:pk>/archivo/", views.evidencia_archivo, name="evidencia_archivo"),
    path("fotos/<uuid:pk>/eliminar/", views.evidencia_eliminar, name="evidencia_eliminar"),
]
