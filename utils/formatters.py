"""Tiny formatting helpers for money and percentages."""


def money(value: float) -> str:
    """1234.5 -> '$1,234.50'."""
    return f"${value:,.2f}"


def signed_money(value: float) -> str:
    """1234.5 -> '+$1,234.50'  ·  -50 -> '-$50.00'."""
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"


def percent(value: float, decimals: int = 2) -> str:
    """12.345 -> '+12.35%'."""
    return f"{value:+.{decimals}f}%"
