"""Failures that must stop an ingest rather than degrade it."""


class IngestError(Exception):
    """Base class for every ingest failure."""


class SourceNotFoundError(IngestError):
    """The source file does not exist at the resolved path."""


class DataQualityError(IngestError):
    """More of the in-scope data was unusable than we are willing to build on.

    Raised rather than logged. A quiet ingest that dropped a third of its rows
    produces a comparable table that looks fine and is not, and every verdict
    resting on it inherits the problem with no way to see it.
    """


class UnknownCategoryError(IngestError):
    """The source introduced a category the normalisation rules do not cover.

    DLD adds property sub-types and area codes between releases. A silent pass
    would either drop a whole neighbourhood or file it under the wrong bedroom
    count, so an unrecognised value stops the ingest and asks for a decision.
    """


class MalformedReleaseError(IngestError):
    """The release does not have the columns the ingest reads.

    DLD publishes the same registry through more than one channel and they do
    not agree on column names, so this is an ordinary situation rather than a
    corrupt file — and it should say which column, not fail inside a query.
    """
