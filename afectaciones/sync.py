"""Sincronización de registros creados sin conexión (RF-20, RNF-06).

El dispositivo genera los UUID de los registros. Reenviar el mismo lote es seguro:
lo que ya existe se reporta como «ya_existia» y no se duplica (riesgo R-02).
Cada registro se guarda por separado: uno inválido no impide guardar los demás.
"""
from agro.alcance import q_unidades, unidad_es_accesible, unidades_de
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from agro.models import Cultivo, UnidadAgricola

from .forms import EvidenciaForm
from .models import Afectacion, EventoSismico, Evidencia, Perdida

MAX_REGISTROS_POR_LOTE = 200
MAX_FOTOS_POR_AFECTACION = 10  # igual que en la pantalla normal (riesgos R-08 y R-20)


def _uuid(valor):
    try:
        return UUID(str(valor))
    except (ValueError, AttributeError, TypeError):
        return None


def _fecha(valor):
    """Convierte texto ISO en fecha con zona horaria; devuelve None si no es válida."""
    if not valor:
        return None
    try:
        f = parse_datetime(str(valor))
    except ValueError:
        return None
    if f is None:
        return None
    if timezone.is_naive(f):
        f = timezone.make_aware(f, timezone.get_current_timezone())
    return f


def _errores(exc):
    if hasattr(exc, "message_dict"):
        return {campo: " ".join(msgs) for campo, msgs in exc.message_dict.items()}
    return {"__all__": " ".join(exc.messages)}


def _creado_en(datos):
    f = _fecha(datos.get("creado_en"))
    if f is None or f > timezone.now():
        return timezone.now()
    return f


def _resultado(pk, estado, **extra):
    return {"id": str(pk) if pk else None, "estado": estado, **extra}


def _guardar_evento(usuario, datos):
    pk = _uuid(datos.get("id"))
    if pk is None:
        return _resultado(None, "error", errores={"id": "Identificador inválido."})

    existente = EventoSismico.objects.filter(pk=pk).first()
    if existente:
        if existente.usuario_id == usuario.pk:
            return _resultado(pk, "ya_existia")
        return _resultado(pk, "error", errores={"id": "Identificador no disponible."})

    unidad = unidades_de(usuario).filter(pk=_uuid(datos.get("unidad_id"))).first()
    if unidad is None:
        return _resultado(pk, "error", errores={"unidad_id": "La unidad agrícola no existe."})

    fecha = _fecha(datos.get("fecha_hora"))
    if fecha is None:
        return _resultado(pk, "error", errores={"fecha_hora": "Fecha y hora inválidas."})

    magnitud = datos.get("magnitud")
    evento = EventoSismico(
        id=pk,
        usuario=usuario,
        unidad=unidad,
        fecha_hora=fecha,
        magnitud=None if magnitud in (None, "") else magnitud,
        epicentro=str(datos.get("epicentro") or "")[:200],
        observaciones=str(datos.get("observaciones") or ""),
        creado_en=_creado_en(datos),
        sincronizado_en=timezone.now(),
    )
    try:
        with transaction.atomic():
            evento.full_clean()
            evento.save(force_insert=True)
    except ValidationError as exc:
        # Mismo sismo (finca + fecha) ya guardado con otro identificador.
        previo = EventoSismico.objects.filter(unidad=unidad, fecha_hora=fecha).first()
        if previo:
            return _resultado(pk, "conflicto", id_existente=str(previo.pk),
                              errores={"fecha_hora": "Ya se registró un sismo en esa unidad y fecha."})
        return _resultado(pk, "error", errores=_errores(exc))
    except IntegrityError:
        return _resultado(pk, "error", errores={"__all__": "No se pudo guardar el sismo."})
    return _resultado(pk, "ok")


def _guardar_afectacion(usuario, datos):
    pk = _uuid(datos.get("id"))
    if pk is None:
        return _resultado(None, "error", errores={"id": "Identificador inválido."})

    existente = Afectacion.objects.filter(pk=pk).select_related("unidad").first()
    if existente:
        if unidad_es_accesible(usuario, existente.unidad):
            return _resultado(pk, "ya_existia")
        return _resultado(pk, "error", errores={"id": "Identificador no disponible."})

    evento = EventoSismico.objects.filter(q_unidades(usuario, "unidad__"), pk=_uuid(datos.get("evento_id"))).first()
    if evento is None:
        return _resultado(pk, "error", errores={"evento_id": "El sismo no existe."})

    # La afectación va siempre sobre la unidad del sismo (una unidad por evento).
    unidad = evento.unidad
    cultivo = None
    if datos.get("cultivo_id"):
        cultivo = Cultivo.objects.filter(pk=_uuid(datos.get("cultivo_id")), unidad=unidad).first()
        if cultivo is None:
            return _resultado(pk, "error", errores={"cultivo_id": "El cultivo no pertenece a la unidad."})

    try:
        area = Decimal(str(datos.get("area_afectada_ha")))
        if not area.is_finite():
            raise InvalidOperation
    except (InvalidOperation, ValueError, TypeError):
        return _resultado(pk, "error", errores={"area_afectada_ha": "El área afectada no es un número válido."})

    afectacion = Afectacion(
        id=pk,
        evento=evento,
        unidad=unidad,
        cultivo=cultivo,
        elemento=datos.get("elemento") or "",
        tipo_dano=datos.get("tipo_dano") or "",
        tipo_dano_otro=str(datos.get("tipo_dano_otro") or "")[:100],
        severidad=datos.get("severidad") or "",
        area_afectada_ha=area,
        ubicacion_texto=str(datos.get("ubicacion_texto") or "")[:200],
        observaciones=str(datos.get("observaciones") or ""),
        creado_en=_creado_en(datos),
        sincronizado_en=timezone.now(),
    )
    perdida_datos = datos.get("perdida") or {}
    try:
        with transaction.atomic():
            afectacion.full_clean()
            afectacion.save(force_insert=True)
            _guardar_perdida(afectacion, cultivo, perdida_datos)
    except ValidationError as exc:
        return _resultado(pk, "error", errores=_errores(exc))
    except IntegrityError:
        return _resultado(pk, "error", errores={"__all__": "No se pudo guardar la afectación."})
    return _resultado(pk, "ok")


def _guardar_perdida(afectacion, cultivo, datos):
    if not isinstance(datos, dict):
        return
    try:
        cantidad = Decimal(str(datos.get("cantidad") or 0))
        valor = Decimal(str(datos.get("valor_estimado_cop") or 0))
        if not (cantidad.is_finite() and valor.is_finite()):
            raise InvalidOperation
    except InvalidOperation:
        raise ValidationError({"perdida": "Los valores de la pérdida no son números válidos."})
    if cantidad <= 0 and valor <= 0:
        return
    perdida = Perdida(
        afectacion=afectacion,
        cultivo=cultivo,
        cantidad=cantidad,
        unidad_medida=datos.get("unidad_medida") or Perdida.UnidadMedida.KG,
        valor_estimado_cop=valor,
        sincronizado_en=timezone.now(),
    )
    try:
        perdida.full_clean()
    except ValidationError as exc:
        raise ValidationError({"perdida": " ".join(exc.messages)})
    perdida.save()


def procesar_lote(usuario, datos):
    """Guarda eventos y luego afectaciones. Devuelve el estado de cada registro."""
    eventos = datos.get("eventos") or []
    afectaciones = datos.get("afectaciones") or []
    if not isinstance(eventos, list) or not isinstance(afectaciones, list):
        raise ValueError("Formato de lote inválido.")
    if len(eventos) + len(afectaciones) > MAX_REGISTROS_POR_LOTE:
        raise OverflowError("El lote supera el máximo permitido.")
    if not all(isinstance(x, dict) for x in eventos + afectaciones):
        raise ValueError("Formato de lote inválido.")

    resultados_eventos = []
    reemplazos = {}  # id enviado -> id existente (cuando hubo conflicto)
    for d in eventos:
        r = _guardar_evento(usuario, d)
        if r["estado"] == "conflicto":
            reemplazos[str(d.get("id"))] = r["id_existente"]
        resultados_eventos.append(r)

    resultados_afect = []
    for d in afectaciones:
        evento_id = str(d.get("evento_id"))
        if evento_id in reemplazos:
            d = {**d, "evento_id": reemplazos[evento_id]}
        resultados_afect.append(_guardar_afectacion(usuario, d))

    return {"eventos": resultados_eventos, "afectaciones": resultados_afect}


def datos_base(usuario):
    """Lo mínimo que el dispositivo necesita para registrar sin conexión."""
    unidades = []
    for u in unidades_de(usuario).prefetch_related("cultivos"):
        unidades.append({
            "id": str(u.pk),
            "nombre": u.nombre,
            "area_ha": str(u.area_ha),
            "cultivos": [
                {"id": str(c.pk), "tipo": c.tipo} for c in u.cultivos.all() if c.activo
            ],
        })
    return {
        "generado": timezone.now().isoformat(),
        "usuario_id": str(usuario.pk),
        "unidades": unidades,
        "catalogos": {
            "elementos": [list(x) for x in Afectacion.Elemento.choices],
            "tipos_dano": [list(x) for x in Afectacion.TipoDano.choices],
            "severidades": [list(x) for x in Afectacion.Severidad.choices],
            "unidades_medida": [list(x) for x in Perdida.UnidadMedida.choices],
        },
    }


def guardar_foto(usuario, datos, archivos):
    """Recibe una fotografía tomada sin conexión. Reenviarla no la duplica."""
    pk = _uuid(datos.get("id"))
    if pk is None:
        return _resultado(None, "error", errores={"id": "Identificador inválido."})

    existente = Evidencia.objects.filter(pk=pk).select_related("afectacion__unidad").first()
    if existente:
        if unidad_es_accesible(usuario, existente.afectacion.unidad):
            return _resultado(pk, "ya_existia")
        return _resultado(pk, "error", errores={"id": "Identificador no disponible."})

    afectacion = Afectacion.objects.filter(
        q_unidades(usuario, "unidad__"), pk=_uuid(datos.get("afectacion_id"))
    ).first()
    if afectacion is None:
        return _resultado(pk, "error", errores={"afectacion_id": "La afectación no existe."})
    if afectacion.evidencias.count() >= MAX_FOTOS_POR_AFECTACION:
        return _resultado(pk, "error", errores={
            "imagen": f"Solo se pueden adjuntar {MAX_FOTOS_POR_AFECTACION} fotografías por afectación."})

    form = EvidenciaForm(
        {"descripcion": str(datos.get("descripcion") or "")[:200]},
        archivos,
        instance=Evidencia(id=pk, afectacion=afectacion, creado_en=_creado_en(datos),
                           sincronizado_en=timezone.now()),
    )
    if not form.is_valid():
        return _resultado(pk, "error", errores={
            campo: " ".join(msgs) for campo, msgs in form.errors.items()})
    form.save()
    return _resultado(pk, "ok")
