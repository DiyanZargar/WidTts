class DomainError(Exception):
    """Base exception for all domain errors."""
    pass


class ConversationTypeNotFoundError(DomainError):
    pass


class SessionNotFoundError(DomainError):
    pass


class InvalidConversationSchemaError(DomainError):
    pass


class DuplicateConversationIdError(DomainError):
    pass
