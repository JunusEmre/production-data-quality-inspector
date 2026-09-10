"""Custom exceptions for the production data quality inspector."""


class ProductionQualityError(Exception):
    """Base error for production data quality inspection."""


class DataLoadError(ProductionQualityError):
    """Raised when a production data file cannot be loaded safely."""
