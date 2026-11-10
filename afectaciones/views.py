from agro.alcance import q_unidades, unidades_de
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
import mimetypes

from django.http import FileResponse, Http404, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from agro.models import UnidadAgricola

from .consultas import describir_filtros, filtrar_afectaciones, resumen_reporte
from .forms import AfectacionForm, EventoForm, EvidenciaForm, HistorialFiltroForm
from .models import Afectacion, EventoSismico, Evidencia, Reporte

MAX_FOTOS = 10  # por afectación (riesgos R-08 y R-20)


def _datos_o_nada(request):
    return request.POST if request.method == "POST" else None


def _evento_del_usuario(request, pk):
    """Un productor solo accede a sus propios sismos (RNF-04)."""
    return get_object_or_404(
        EventoSismico.objects.select_related("unidad").filter(q_unidades(request.user, "unidad__")), pk=pk
    )


def _afectacion_del_usuario(request, pk):
    return get_object_or_404(
        Afectacion.objects.select_related("evento", "unidad", "cultivo").filter(q_unidades(request.user, "unidad__")),
        pk=pk,
    )


@login_required
def eventos_lista(request):
    eventos = (
        EventoSismico.objects.filter(q_unidades(request.user, "unidad__"))
        .select_related("unidad")
        .annotate(num_afectaciones=Count("afectaciones"))
    )
    return render(request, "afectaciones/evento_lista.html", {"eventos": eventos})


@login_required
def evento_crear(request):
    if not unidades_de(request.user).exists():
        messages.info(request, "Primero registra una unidad agrícola para poder anotar un sismo.")
        return redirect("unidad_crear")
    form = EventoForm(
        _datos_o_nada(request), instance=EventoSismico(usuario=request.user), usuario=request.user
    )
    if request.method == "POST" and form.is_valid():
        evento = form.save(commit=False)
        evento.sincronizado_en = timezone.now()
        evento.save()
        messages.success(request, "Sismo registrado. Ahora puedes anotar sus afectaciones.")
        return redirect("evento_detalle", pk=evento.pk)
    contexto = {"form": form, "titulo": "Registrar sismo", "volver": reverse("eventos")}
    return render(request, "agro/formulario.html", contexto)


@login_required
def evento_detalle(request, pk):
    evento = _evento_del_usuario(request, pk)
    afectaciones = evento.afectaciones.select_related("cultivo")
    return render(
        request,
        "afectaciones/evento_detalle.html",
        {"evento": evento, "afectaciones": afectaciones},
    )


@login_required
def evento_editar(request, pk):
    evento = _evento_del_usuario(request, pk)
    form = EventoForm(_datos_o_nada(request), instance=evento, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        evento = form.save(commit=False)
        evento.sincronizado_en = timezone.now()
        evento.save()
        messages.success(request, "Cambios guardados.")
        return redirect("evento_detalle", pk=evento.pk)
    contexto = {
        "form": form,
        "titulo": "Editar sismo",
        "volver": reverse("evento_detalle", args=[evento.pk]),
    }
    return render(request, "agro/formulario.html", contexto)


@login_required
def afectacion_crear(request, pk):
    evento = _evento_del_usuario(request, pk)
    # La afectación siempre queda en la misma unidad que su sismo.
    instancia = Afectacion(evento=evento, unidad=evento.unidad)
    form = AfectacionForm(_datos_o_nada(request), instance=instancia, evento=evento)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            afectacion = form.save(commit=False)
            afectacion.sincronizado_en = timezone.now()
            afectacion.save()
            form.guardar_perdida(afectacion)
        messages.success(request, "Afectación registrada.")
        return redirect("afectacion_detalle", pk=afectacion.pk)
    contexto = {
        "form": form,
        "titulo": f"Registrar afectación en {evento.unidad.nombre}",
        "volver": reverse("evento_detalle", args=[evento.pk]),
    }
    return render(request, "agro/formulario.html", contexto)


@login_required
def afectacion_detalle(request, pk):
    afectacion = _afectacion_del_usuario(request, pk)
    return render(
        request,
        "afectaciones/afectacion_detalle.html",
        {
            "afectacion": afectacion,
            "perdidas": afectacion.perdidas.all(),
            "evidencias": afectacion.evidencias.all(),
        },
    )


@login_required
def afectacion_editar(request, pk):
    afectacion = _afectacion_del_usuario(request, pk)
    form = AfectacionForm(_datos_o_nada(request), instance=afectacion, evento=afectacion.evento)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            afectacion = form.save(commit=False)
            afectacion.sincronizado_en = timezone.now()
            afectacion.save()
            form.guardar_perdida(afectacion)
        messages.success(request, "Cambios guardados.")
        return redirect("afectacion_detalle", pk=afectacion.pk)
    contexto = {
        "form": form,
        "titulo": "Editar afectación",
        "volver": reverse("afectacion_detalle", args=[afectacion.pk]),
    }
    return render(request, "agro/formulario.html", contexto)


@login_required
def evidencia_agregar(request, pk):
    afectacion = _afectacion_del_usuario(request, pk)
    if afectacion.evidencias.count() >= MAX_FOTOS:
        messages.error(request, f"Solo se pueden adjuntar {MAX_FOTOS} fotografías por afectación.")
        return redirect("afectacion_detalle", pk=afectacion.pk)
    publicar = request.method == "POST"
    form = EvidenciaForm(
        request.POST if publicar else None,
        request.FILES if publicar else None,
        instance=Evidencia(afectacion=afectacion),
    )
    if publicar and form.is_valid():
        evidencia = form.save(commit=False)
        evidencia.sincronizado_en = timezone.now()
        evidencia.save()
        messages.success(request, "Fotografía agregada.")
        return redirect("afectacion_detalle", pk=afectacion.pk)
    contexto = {
        "form": form,
        "titulo": "Agregar fotografía",
        "volver": reverse("afectacion_detalle", args=[afectacion.pk]),
        "con_archivos": True,
    }
    return render(request, "agro/formulario.html", contexto)


@login_required
def evidencia_archivo(request, pk):
    """Entrega la fotografía solo a quien pertenece a la finca (las fotos ya no son públicas)."""
    evidencia = get_object_or_404(
        Evidencia.objects.filter(q_unidades(request.user, "afectacion__unidad__")), pk=pk
    )
    try:
        archivo = evidencia.imagen.open("rb")
    except (FileNotFoundError, ValueError):
        raise Http404("La fotografía no está disponible.")
    tipo = mimetypes.guess_type(evidencia.imagen.name)[0] or "application/octet-stream"
    respuesta = FileResponse(archivo, content_type=tipo)
    respuesta["Cache-Control"] = "private, max-age=3600"
    return respuesta


@login_required
@require_POST
def evidencia_eliminar(request, pk):
    evidencia = get_object_or_404(
        Evidencia.objects.filter(q_unidades(request.user, "afectacion__unidad__")), pk=pk
    )
    afectacion_pk = evidencia.afectacion_id
    almacenamiento, nombre = evidencia.imagen.storage, evidencia.imagen.name
    evidencia.delete()
    if nombre:
        almacenamiento.delete(nombre)
    messages.success(request, "Fotografía eliminada.")
    return redirect("afectacion_detalle", pk=afectacion_pk)


@login_required
def historial(request):
    """Historial de afectaciones con filtros y resumen (RF-15, RF-16)."""
    form = HistorialFiltroForm(request.GET or None, usuario=request.user)
    filtros = form.cleaned_data if form.is_valid() else {}
    base = filtrar_afectaciones(request.user, **filtros)
    resumen = base.aggregate(
        total=Count("id", distinct=True), valor=Sum("perdidas__valor_estimado_cop")
    )
    listado = base.annotate(valor_perdido=Sum("perdidas__valor_estimado_cop")).order_by(
        "-evento__fecha_hora", "-creado_en"
    )
    pagina = Paginator(listado, 20).get_page(request.GET.get("page"))
    parametros = request.GET.copy()
    parametros.pop("page", None)
    contexto = {
        "form": form,
        "pagina": pagina,
        "resumen": resumen,
        "querystring": parametros.urlencode(),
    }
    return render(request, "afectaciones/historial.html", contexto)


@login_required
def reporte(request):
    """Vista previa del reporte con los mismos filtros del historial (RF-17)."""
    form = HistorialFiltroForm(request.GET or None, usuario=request.user)
    filtros = form.cleaned_data if form.is_valid() else {}
    afectaciones = filtrar_afectaciones(request.user, **filtros)
    return render(
        request,
        "afectaciones/reporte.html",
        {"form": form, "resumen": resumen_reporte(afectaciones)},
    )


@login_required
@require_POST
def reporte_pdf(request):
    """Genera el PDF, guarda el reporte y lo entrega como descarga (RF-18)."""
    form = HistorialFiltroForm(request.POST, usuario=request.user)
    if not form.is_valid():
        messages.error(request, "Los filtros del reporte no son válidos. Revísalos e inténtalo de nuevo.")
        return redirect("reporte")

    filtros = form.cleaned_data
    afectaciones = filtrar_afectaciones(request.user, **filtros)
    if not afectaciones.exists():
        messages.warning(request, "No hay afectaciones con esos filtros, así que no se generó el reporte.")
        return redirect("reporte")

    try:
        # Se importa aquí para que el resto del sitio funcione aunque falte instalar reportlab.
        from .pdf import generar_pdf, formato_cop, formato_ha
    except ImportError:
        messages.error(request, "Falta instalar la librería de PDF (reportlab). Consulta al administrador.")
        return redirect("reporte")

    resumen = resumen_reporte(afectaciones)
    detalle = afectaciones.annotate(valor_perdido=Sum("perdidas__valor_estimado_cop")).order_by(
        "-evento__fecha_hora", "-creado_en"
    )
    filas = [
        [
            timezone.localtime(a.evento.fecha_hora).strftime("%d/%m/%Y %H:%M"),
            a.unidad.nombre,
            a.tipo_dano_texto,
            a.get_elemento_display(),
            a.get_severidad_display(),
            formato_ha(a.area_afectada_ha),
            formato_cop(a.valor_perdido) if a.valor_perdido else "-",
        ]
        for a in detalle
    ]
    contenido = generar_pdf(
        productor=request.user.get_full_name() or request.user.get_username(),
        generado=timezone.localtime().strftime("%d/%m/%Y %H:%M"),
        filtros=describir_filtros(filtros),
        resumen=resumen,
        severidades=[(etiqueta, n) for etiqueta, n, _ in resumen["por_severidad"]],
        unidades=[(u["unidad__nombre"], u["n"]) for u in resumen["por_unidad"]],
        filas=filas,
        finca=request.user.finca.nombre if request.user.finca_id else "",
    )

    with transaction.atomic():
        registro = Reporte.objects.create(
            usuario=request.user,
            formato=Reporte.Formato.PDF,
            fecha_desde=filtros.get("desde"),
            fecha_hasta=filtros.get("hasta"),
        )
        registro.afectaciones.set(list(afectaciones))

    respuesta = HttpResponse(contenido, content_type="application/pdf")
    nombre = f"reporte-agrosismo-{timezone.localdate():%Y%m%d}.pdf"
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return respuesta
