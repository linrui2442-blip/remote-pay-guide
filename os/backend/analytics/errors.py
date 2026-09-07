import re


class AnalyticsCollectionNotReady(RuntimeError):
    """Raised when a platform analytics adapter cannot collect safely."""


def sanitize_analytics_error(error, *, max_length=500):
    """Return a bounded operational error without credential material."""
    text = str(error or "")[:max_length]
    patterns = (
        r"(?i)(access[_-]?token|refresh[_-]?token|api[_-]?key|client[_-]?secret|authorization)(\s*[=:]\s*)([^\s&,;]+)",
        r"(?i)(bearer)(\s+)([^\s,;]+)",
    )
    for pattern in patterns:
        text = re.sub(pattern, r"\1\2[redacted]", text)
    return text

