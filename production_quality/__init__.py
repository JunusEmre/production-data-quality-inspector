"""Production Data Quality Inspector.

Stage 2 exposes configuration, safe CSV loading, the validation-rule catalog,
and the Pandera validation engine. Importing this package does not read
production files, write output, or run validation.
"""

from production_quality.config import PRODUCTION_DATA_CONFIG, ProductionDataConfig
from production_quality.data import load_production_data
from production_quality.exceptions import DataLoadError
from production_quality.manual_validation import validate_with_pandas
from production_quality.models import ValidationIssue, ValidationResult
from production_quality.rules import VALIDATION_RULES, ValidationRule

__all__ = [
    "PRODUCTION_DATA_CONFIG",
    "ProductionDataConfig",
    "DataLoadError",
    "load_production_data",
    "ValidationRule",
    "VALIDATION_RULES",
    "ValidationIssue",
    "ValidationResult",
    "build_production_schema",
    "validate_with_pandera",
    "validate_file_with_pandera",
    "validate_with_pandas",
]

_LAZY_EXPORTS = {
    "build_production_schema": ("production_quality.schema", "build_production_schema"),
    "validate_with_pandera": ("production_quality.validation", "validate_with_pandera"),
    "validate_file_with_pandera": (
        "production_quality.validation",
        "validate_file_with_pandera",
    ),
}


def __getattr__(name: str):
    """Load Pandera helpers only when they are first used."""

    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_EXPORTS[name]
    module = __import__(module_name, fromlist=[attr_name])
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_EXPORTS.keys()))
