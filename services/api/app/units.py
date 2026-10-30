"""Small unit system: just enough to convert within a physical dimension, and to refuse anything else."""
from __future__ import annotations

# canonical unit -> (dimension, factor to the dimension's base unit)
DIMS: dict[str, tuple[str, float]] = {
    "V": ("voltage", 1.0), "mV": ("voltage", 1e-3), "kV": ("voltage", 1e3),
    "A": ("current", 1.0), "mA": ("current", 1e-3),
    "W": ("power", 1.0), "kW": ("power", 1e3),
    "Wh": ("energy", 1.0), "kWh": ("energy", 1e3),
    "kg": ("mass", 1.0), "g": ("mass", 1e-3),
    "USD": ("money", 1.0),
    "rpm": ("speed", 1.0),
    "mm": ("length", 1.0), "cm": ("length", 10.0), "m": ("length", 1000.0),
    "h": ("time", 1.0),
    "m/s": ("velocity", 1.0),
}

_ALIASES = {
    "v": "V", "volt": "V", "volts": "V", "mv": "mV", "kv": "kV",
    "a": "A", "amp": "A", "amps": "A", "ampere": "A", "amperes": "A", "ma": "mA",
    "w": "W", "watt": "W", "watts": "W", "kw": "kW",
    "wh": "Wh", "kwh": "kWh",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg", "g": "g", "gram": "g", "grams": "g",
    "usd": "USD", "$": "USD", "dollar": "USD", "dollars": "USD",
    "rpm": "rpm", "mm": "mm", "cm": "cm", "m": "m",
    "h": "h", "hr": "h", "hrs": "h", "hour": "h", "hours": "h",
    "m/s": "m/s", "mps": "m/s",
}


class UnitError(ValueError):
    pass


def normalize_unit(unit: str) -> str:
    u = (unit or "").strip()
    if u in DIMS:
        return u
    low = u.lower()
    if low in _ALIASES:
        return _ALIASES[low]
    raise UnitError(f"Unknown unit '{unit}'.")


def dimension(unit: str) -> str:
    return DIMS[normalize_unit(unit)][0]


def convert(value: float, from_unit: str, to_unit: str) -> float:
    a, b = normalize_unit(from_unit), normalize_unit(to_unit)
    if a == b:
        return float(value)
    (da, fa), (db, fb) = DIMS[a], DIMS[b]
    if da != db:
        raise UnitError(f"Cannot convert {a} ({da}) to {b} ({db}).")
    return float(value) * fa / fb


def fmt(value: float | None, unit: str = "", digits: int = 3) -> str:
    """Human-friendly number, e.g. 24 V, 0.42 kg, 1.88 m/s."""
    if value is None:
        return "unknown"
    if abs(value - round(value)) < 1e-9:
        s = f"{int(round(value))}"
    else:
        s = f"{value:.{digits}g}"
    return f"{s} {unit}".strip()
