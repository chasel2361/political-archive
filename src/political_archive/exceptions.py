"""Application-specific exceptions."""


class PoliticalArchiveError(Exception):
    """Base exception for expected application errors."""


class ConfigurationError(PoliticalArchiveError):
    """Raised when project configuration cannot be loaded or validated."""
