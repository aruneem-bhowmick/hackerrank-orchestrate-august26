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


class MediaIngestionError(DatasetError):
    """Raised when the media ingestion stage cannot produce a normalized message for every row."""


class OCRClientError(MediaIngestionError):
    """Raised when an OCR client cannot produce a result for an image.

    Covers a missing API key, a network/API failure, or a response that
    cannot be parsed — never raised for a well-formed response that simply
    found no readable text, which is a normal OCRResult(failure=True), not
    an error.
    """


class ASRClientError(MediaIngestionError):
    """Raised when an ASR client cannot produce a result for a voice note.

    Covers a missing API key, a network/API failure, or a response that
    cannot be parsed — never raised for a well-formed response that simply
    found no speech, which is a normal ASRResult(failure=True), not an
    error.
    """


class PersonalizationError(DatasetError):
    """Raised when personalization cannot produce one bundle per message."""


class DecisionFusionError(DatasetError):
    """Raised when decision fusion cannot produce one Decision Record per message.

    Also raised by a self-check that catches a message_type value outside
    the fixed allowed-value list, which should be unreachable given the
    selector's own exhaustive branches — see
    router.decision.message_type.validate_message_type.
    """
