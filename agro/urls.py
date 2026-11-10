from django.urls import path

from . import views

urlpatterns = [
    path("unidades/", views.unidades_lista, name="unidades"),
    path("unidades/nueva/", views.unidad_crear, name="unidad_crear"),
    path("unidades/<uuid:pk>/", views.unidad_detalle, name="unidad_detalle"),
    path("unidades/<uuid:pk>/editar/", views.unidad_editar, name="unidad_editar"),
    path("unidades/<uuid:pk>/cultivos/nuevo/", views.cultivo_crear, name="cultivo_crear"),
    path("cultivos/<uuid:pk>/editar/", views.cultivo_editar, name="cultivo_editar"),
]
