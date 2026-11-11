from datetime import date, datetime
from decimal import Decimal


def money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{Decimal(value).quantize(Decimal('0.01'))}"


def money4(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{Decimal(value).quantize(Decimal('0.0001'))}"


def stamp(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def num(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(Decimal(value), "f")
