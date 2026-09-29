"""Errors the interface can show directly to the student."""


class TutorError(Exception):
    """A problem explained in plain language."""


class ScannedDocumentError(TutorError):
    """The file has no usable text layer."""
