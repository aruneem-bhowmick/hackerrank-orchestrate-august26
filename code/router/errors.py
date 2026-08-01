"""Exception types shared across the dataset load and validation stage."""


class DatasetError(Exception):
    """Base class for every dataset load/validation failure in this system."""


class DatasetSchemaError(DatasetError):
    """Raised when a dataset file is missing, unreadable, or missing required columns."""
