"""
Exception hierarchy for VoteMarket Toolkit.

Exception Categories:
- RetryableException: Transient failures that may succeed on retry (RPC, network)
- NonRetryableException: Permanent failures that won't benefit from retry (bad data)
- ConfigurationException: Startup/config errors that prevent operation

Existing exceptions are categorized:
- VoteMarketProofsException -> RetryableException (RPC failures during proof generation)
- VoteMarketDataException -> NonRetryableException (invalid/missing data)
- APIException -> RetryableException (transient network failures)
"""


class RetryableException(Exception):
    """
    Base class for exceptions that may succeed on retry.

    Use for transient failures like:
    - RPC timeouts
    - Rate limiting
    - Temporary network issues
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NonRetryableException(Exception):
    """
    Base class for exceptions that won't benefit from retry.

    Use for permanent failures like:
    - Invalid input data
    - Missing required data
    - Business logic violations
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ConfigurationException(NonRetryableException):
    """
    Exception for configuration/startup errors.

    Use when:
    - Required environment variables are missing
    - Invalid configuration values
    - Missing required resources
    """

    pass


class VoteMarketProofsException(RetryableException):
    """
    Exception for proof generation failures.

    Inherits from RetryableException because proof generation
    failures are often due to RPC issues that may resolve on retry.
    """

    pass


class VoteMarketDataException(NonRetryableException):
    """
    Exception for data retrieval/validation failures.

    Inherits from NonRetryableException because data issues
    (missing votes, invalid addresses) won't resolve on retry.
    """

    pass


class APIException(RetryableException):
    """
    Exception for external API failures.

    Inherits from RetryableException because API failures
    are often transient (rate limits, timeouts).
    """

    pass
