"""Filtros para mostrar números con separador de miles colombiano (puntos)."""
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def _entero(valor):
    try:
        return int(Decimal(valor or 0).quantize(Decimal("1")))
    except (InvalidOperation, ValueError, TypeError):
        return 0


@register.filter
def miles(valor):
    """1533333 -> '1.533.333'."""
    return f"{_entero(valor):,}".replace(",", ".")


@register.filter
def ha(valor):
    """31.0200000000 -> '31,02'; 1250.5 -> '1.250,50' (hectáreas con dos decimales)."""
    try:
        n = Decimal(valor or 0).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        n = Decimal("0.00")
    return f"{n:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")


@register.filter
def cop(valor):
    """1533333 -> '$1.533.333'."""
    return "$" + miles(valor)
