"""Cifras y gráficas del Inicio: resumen de lo que el productor ha registrado.

Todo se calcula solo con los datos del propio usuario (RNF-04). Los números que van
dentro de gráficas SVG se entregan ya como texto con punto decimal, para que la
localización en español no los vuelva coma y rompa el dibujo.
"""
from agro.alcance import q_unidades
from datetime import date, datetime, time, timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from .models import Afectacion, Perdida

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
COLORES_SEVERIDAD = {"LEVE": "#4c9a5c", "MODERADA": "#e0a526", "GRAVE": "#c94a3d"}


def pesos(valor):
    """1234567 -> '$1.234.567'."""
    return "$" + f"{int(valor or 0):,}".replace(",", ".")


def _barras(filas):
    """[(etiqueta, valor, texto)] -> lista con el ancho (0-100) relativo al mayor."""
    mayor = max((v for _, v, _ in filas), default=0)
    return [
        {"etiqueta": e, "valor": v, "texto": t, "ancho": max(6, round(v * 100 / mayor)) if mayor else 0}
        for e, v, t in filas
    ]


def _ultimos_meses(n=6):
    hoy = timezone.localdate()
    y, m = hoy.year, hoy.month
    meses = []
    for _ in range(n):
        meses.append(date(y, m, 1))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(meses))


# Periodos de la gráfica del Inicio: clave -> texto del botón.
PERIODOS = {"7d": "7 días", "3": "3 meses", "6": "6 meses", "12": "12 meses"}
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def _serie(afectaciones, periodo):
    """Devuelve [(etiqueta, cantidad)] por día (7 días) o por mes (3, 6 o 12).

    Se agrupa en Python (no con __date ni TruncMonth): en MySQL esos filtros dependen de
    tablas de zonas horarias que no siempre están cargadas y devolverían 0.
    """
    zona = timezone.get_current_timezone()
    if periodo == "7d":
        hoy = timezone.localdate()
        dias = [hoy - timedelta(days=i) for i in range(6, -1, -1)]
        desde = timezone.make_aware(datetime.combine(dias[0], time.min), zona)
        cuenta = {}
        for fecha in afectaciones.filter(evento__fecha_hora__gte=desde).values_list("evento__fecha_hora", flat=True):
            d = timezone.localtime(fecha).date()
            cuenta[d] = cuenta.get(d, 0) + 1
        return [(f"{DIAS[d.weekday()]} {d.day}", cuenta.get(d, 0)) for d in dias]
    meses = _ultimos_meses(int(periodo))
    desde = timezone.make_aware(datetime.combine(meses[0], time.min), zona)
    cuenta = {}
    for fecha in afectaciones.filter(evento__fecha_hora__gte=desde).values_list("evento__fecha_hora", flat=True):
        local = timezone.localtime(fecha)
        cuenta[(local.year, local.month)] = cuenta.get((local.year, local.month), 0) + 1
    return [(MESES[d.month - 1], cuenta.get((d.year, d.month), 0)) for d in meses]


def resumen(usuario, periodo="6"):
    afectaciones = Afectacion.objects.filter(q_unidades(usuario, "unidad__"))
    total = afectaciones.count()
    datos = {"total": total, "hay_datos": total > 0}
    if not total:
        return datos

    # Severidad (dona)
    por_sev = dict(afectaciones.values_list("severidad").annotate(n=Count("id")))
    segmentos, acumulado = [], 0.0
    for clave, etiqueta in Afectacion.Severidad.choices:
        n = por_sev.get(clave, 0)
        if not n:
            continue
        pct = n * 100 / total
        segmentos.append({
            "clave": clave, "etiqueta": etiqueta, "n": n, "color": COLORES_SEVERIDAD[clave],
            "porcentaje": round(pct), "trazo": f"{pct:.2f}", "resto": f"{100 - pct:.2f}",
            "desfase": f"{25 - acumulado:.2f}",
        })
        acumulado += pct
    datos["severidad"] = segmentos

    # Tipo de daño
    nombres = dict(Afectacion.TipoDano.choices)
    por_tipo = afectaciones.values_list("tipo_dano").annotate(n=Count("id")).order_by("-n")
    datos["tipos"] = _barras([(nombres.get(t, t), n, str(n)) for t, n in por_tipo])

    # Afectaciones por día (últimos 7) o por mes (últimos 3, 6 o 12)
    periodo = str(periodo) if str(periodo) in PERIODOS else "6"
    datos["periodo"] = periodo
    datos["periodo_texto"] = "últimos " + PERIODOS[periodo]
    datos["n_barras"] = 7 if periodo == "7d" else int(periodo)
    serie = _serie(afectaciones, periodo)
    mayor = max(n for _, n in serie)
    datos["meses"] = [
        {"etiqueta": e, "n": n, "alto": (max(8, round(n * 100 / mayor)) if n else 0)} for e, n in serie
    ]
    datos["meses_total"] = sum(n for _, n in serie)
    datos["opciones_periodo"] = [{"clave": k, "texto": t, "activa": k == periodo} for k, t in PERIODOS.items()]

    # Pérdidas
    perdidas = Perdida.objects.filter(q_unidades(usuario, "afectacion__unidad__"))
    datos["perdida_total"] = pesos(perdidas.aggregate(t=Sum("valor_estimado_cop"))["t"])
    datos["area_total"] = f"{afectaciones.aggregate(t=Sum('area_afectada_ha'))['t'] or 0:.1f}".replace(".", ",")
    por_unidad = (
        perdidas.values_list("afectacion__unidad__nombre")
        .annotate(t=Sum("valor_estimado_cop")).order_by("-t")[:5]
    )
    datos["perdida_unidades"] = _barras([(n, t, pesos(t)) for n, t in por_unidad if t])
    return datos
