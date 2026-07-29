from app.modules.interruption.domain.interfaces.interruption_repository_interface import (
    InterruptionRepositoryInterface,
)


class RecordInterruption:

    def __init__(self, interruption_repository: InterruptionRepositoryInterface):
        self._interruption_repository = interruption_repository

    def execute(self, session_id: str, interruption_type: str, interruption_text: str) -> None:
        self._interruption_repository.add(session_id, interruption_type, interruption_text)
