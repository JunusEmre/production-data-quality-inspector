"""Production Data Quality Inspector.

Stage 1 exposes configuration, safe CSV loading, and the validation-rule
catalog. Importing this package does not read production files or write
output.
"""

from production_quality.config import PRODUCTION_DATA_CONFIG, ProductionDataConfig
from production_quality.data import load_production_data
from production_quality.exceptions import DataLoadError
from production_quality.rules import VALIDATION_RULES, ValidationRule

__all__ = [
    "PRODUCTION_DATA_CONFIG",
    "ProductionDataConfig",
    "DataLoadError",
    "load_production_data",
    "ValidationRule",
    "VALIDATION_RULES",
]
