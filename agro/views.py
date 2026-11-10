from .alcance import q_unidades, unidades_de
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .divipola import DEPARTAMENTOS
from .forms import CultivoForm, UnidadForm
from .models import Cultivo, UnidadAgricola

TIPOS_CULTIVO_COMUNES = ["Café", "Plátano", "Yuca", "Caña de azúcar", "Frutales", "Maíz", "Cacao"]


def _unidad_del_usuario(request, pk):
    """Un productor solo puede acceder a sus propias unidades (RNF-04)."""
    return get_object_or_404(unidades_de(request.user), pk=pk)


def _datos_o_nada(request):
    return request.POST if request.method == "POST" else None


@login_required
def unidades_lista(request):
    q = request.GET.get("q", "").strip()
    unidades = unidades_de(request.user).annotate(
        num_cultivos=Count("cultivos", filter=Q(cultivos__activo=True))
    )
    if q:
        unidades = unidades.filter(nombre__icontains=q)
    return render(request, "agro/unidad_lista.html", {"unidades": unidades, "q": q})


@login_required
def unidad_crear(request):
    form = UnidadForm(_datos_o_nada(request), propietario=request.user)
    if request.method == "POST" and form.is_valid():
        unidad = form.save(commit=False)
        unidad.propietario = request.user
        unidad.sincronizado_en = timezone.now()
        unidad.save()
        messages.success(request, "Unidad agrícola guardada.")
        return redirect("unidad_detalle", pk=unidad.pk)
    contexto = {"form": form, "titulo": "Nueva unidad agrícola", "volver": reverse("unidades"), "divipola": DEPARTAMENTOS}
    return render(request, "agro/formulario.html", contexto)


@login_required
def unidad_detalle(request, pk):
    unidad = _unidad_del_usuario(request, pk)
    return render(
        request, "agro/unidad_detalle.html", {"unidad": unidad, "cultivos": unidad.cultivos.all()}
    )


@login_required
def unidad_editar(request, pk):
    unidad = _unidad_del_usuario(request, pk)
    form = UnidadForm(_datos_o_nada(request), instance=unidad, propietario=request.user)
    if request.method == "POST" and form.is_valid():
        unidad = form.save(commit=False)
        unidad.sincronizado_en = timezone.now()
        unidad.save()
        messages.success(request, "Cambios guardados.")
        return redirect("unidad_detalle", pk=unidad.pk)
    contexto = {
        "form": form,
        "titulo": f"Editar {unidad.nombre}",
        "volver": reverse("unidad_detalle", args=[unidad.pk]),
        "divipola": DEPARTAMENTOS,
    }
    return render(request, "agro/formulario.html", contexto)


@login_required
def cultivo_crear(request, pk):
    unidad = _unidad_del_usuario(request, pk)
    form = CultivoForm(_datos_o_nada(request), unidad=unidad)
    if request.method == "POST" and form.is_valid():
        cultivo = form.save(commit=False)
        cultivo.unidad = unidad
        cultivo.sincronizado_en = timezone.now()
        cultivo.save()
        messages.success(request, "Cultivo agregado.")
        return redirect("unidad_detalle", pk=unidad.pk)
    contexto = {
        "form": form,
        "titulo": f"Nuevo cultivo en {unidad.nombre}",
        "volver": reverse("unidad_detalle", args=[unidad.pk]),
        "tipos_cultivo": TIPOS_CULTIVO_COMUNES,
    }
    return render(request, "agro/formulario.html", contexto)


@login_required
def cultivo_editar(request, pk):
    cultivo = get_object_or_404(
        Cultivo.objects.select_related("unidad").filter(q_unidades(request.user, "unidad__")), pk=pk
    )
    unidad = cultivo.unidad
    form = CultivoForm(_datos_o_nada(request), instance=cultivo, unidad=unidad)
    if request.method == "POST" and form.is_valid():
        cultivo = form.save(commit=False)
        cultivo.sincronizado_en = timezone.now()
        cultivo.save()
        messages.success(request, "Cultivo actualizado.")
        return redirect("unidad_detalle", pk=unidad.pk)
    contexto = {
        "form": form,
        "titulo": f"Editar cultivo de {unidad.nombre}",
        "volver": reverse("unidad_detalle", args=[unidad.pk]),
        "tipos_cultivo": TIPOS_CULTIVO_COMUNES,
    }
    return render(request, "agro/formulario.html", contexto)
