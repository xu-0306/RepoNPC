"""Application-owned parse diagnostics; never copy arbitrary response data."""

from enum import StrEnum

from reponpc.providers.contracts import ProviderError, ProviderFailureCode


class ResponseIssue(StrEnum):
    JSON = "HTTP 200; response body is not a JSON object."
    CHOICES = "HTTP 200; expected exactly one item in choices."
    MESSAGE = "HTTP 200; the assistant message object is missing or invalid."
    CONTENT = "HTTP 200; the assistant content is empty or has an unsupported type."
    OUTPUT_LIMIT = "HTTP 200; the response reached the output limit (length)."
    FINISH_REASON = "HTTP 200; the response finish reason is missing or invalid."
    USAGE = "HTTP 200; token usage fields are invalid."
    REQUEST_ID = "HTTP 200; the response id is not a string."


class ProviderResponseError(ProviderError):
    """Keep the stable failure code while identifying our failed parser check."""

    def __init__(self, issue: ResponseIssue) -> None:
        if not isinstance(issue, ResponseIssue):
            raise TypeError("issue must be a ResponseIssue")
        super().__init__(ProviderFailureCode.INVALID_RESPONSE)
        self.issue = issue
        self.diagnostic_message = f"RepoNPC response check: {issue.value}"
