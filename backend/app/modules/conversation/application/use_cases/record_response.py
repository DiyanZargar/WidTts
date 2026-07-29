from app.modules.conversation.domain.interfaces.response_repository_interface import (
    ResponseRepositoryInterface,
)


class RecordResponse:

    def __init__(self, response_repository: ResponseRepositoryInterface):
        self._response_repository = response_repository

    def execute(self, sequence: int, session_id: str, user_response: str, validation_result: str) -> None:
        self._response_repository.add(sequence, session_id, user_response, validation_result)
