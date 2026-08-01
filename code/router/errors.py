"""Exception types shared across the dataset load and validation stage."""


class DatasetError(Exception):
    """Base class for every dataset load/validation failure in this system."""


class DatasetSchemaError(DatasetError):
    """Raised when a dataset file is missing, unreadable, or missing required columns."""


class DatasetIntegrityError(DatasetError):
    """Raised when an organizer-only or hidden ground-truth file is discoverable."""


class TimelineJoinError(DatasetError):
    """Raised when message_history and message_events cannot be joined consistently."""


class RowCountParityError(DatasetError):
    """Raised when messages.csv and output.csv row counts or message_id sets disagree."""


class SafetyGateError(DatasetError):
    """Raised when the safety gate cannot produce a verdict for every message."""
