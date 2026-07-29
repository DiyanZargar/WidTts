from abc import ABC, abstractmethod


class ResponseRepositoryInterface(ABC):

    @abstractmethod
    def add(self, sequence: int, session_id: str, user_response: str, validation_result: str) -> None:
        raise NotImplementedError
