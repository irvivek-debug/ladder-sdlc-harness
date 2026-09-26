"""Station plant twins with fault injection."""
from .base import NullPlant, Plant
from .st10_conveyor import St10Plant
from .st20_leaktest import St20Plant
from .st30_hipot import St30Plant

PLANTS: dict[str, type[Plant]] = {"none": NullPlant, "st10": St10Plant, "st20": St20Plant, "st30": St30Plant}

__all__ = ["PLANTS", "Plant", "NullPlant", "St10Plant", "St20Plant", "St30Plant"]
