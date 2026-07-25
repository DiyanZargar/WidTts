# Backend Implementation (FastAPI, Modular Monolith, Clean Architecture)

All backend code organized by module with Clean Architecture layers.
Dependencies always point inward: Presentation → Application → Domain ← Infrastructure.
Every module is self-contained. Domain layer uses `abc.ABC` with `@abstractmethod` for interfaces.
Application layer use cases are classes with an `execute()` method.

---

## Shared Layer

### shared/config/settings.py

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    deepgram_api_key: str
    database_path: str = "app.db"
    ai_validation_model: str = "claude-sonnet-4-6"
    max_retries_per_item: int = 3

    class Config:
        env_file = ".env"


settings = Settings()
```

### shared/constants/conversation_types.py

```python
CONVERSATION_TYPES = [
    "daily_life_companion",
    "career_life_advisor",
    "health_wellness_assistant",
    "travel_planner",
]
```

### shared/constants/states.py

```python
STATES = [
    "welcoming",
    "asking",
    "listening",
    "validating",
    "speaking",
    "repeating",
    "completed",
]
```

### shared/constants/interruption_types.py

```python
INTERRUPTION_TYPES = ["stop", "cancel", "repeat", "correction"]
```

### shared/logging/logger.py

```python
import logging

logger = logging.getLogger("conversation_widget")
logging.basicConfig(level=logging.INFO)
```

### shared/exceptions/domain_exceptions.py

```python
class ConversationTypeNotFoundError(Exception):
    pass


class SessionNotFoundError(Exception):
    pass


class ScriptAlreadyLoadedError(Exception):
    pass
```

### shared/database/db.py

```python
import sqlite3
from contextlib import contextmanager
from app.shared.config.settings import settings


@contextmanager
def get_connection():
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
```

### shared/database/init_db.py

Table creation runs through the versioned migration system.
Full migration file contents, the runner, and the step-by-step workflow
for writing new migrations are in `05-database-migrations.md`. This
function is what `main.py` calls on startup.

```python
from app.shared.database.migrations.runner import run_migrations


def init_db():
    run_migrations()
```

### shared/schemas/session_schema.py

```python
from pydantic import BaseModel


class SessionState(BaseModel):
    session_id: str
    conversation_type: str
    status: str
    current_question_index: int
    current_state: str
    retries: int
```

### shared/schemas/message_schema.py

```python
from pydantic import BaseModel


class MessageIn(BaseModel):
    session_id: str
    sender: str
    text: str
```

### shared/schemas/ws_schema.py

```python
from pydantic import BaseModel
from typing import Optional, Literal


class WSEvent(BaseModel):
    event: Literal[
        "session_started", "question", "instruction", "validation_result",
        "tts_audio", "tts_stop", "session_completed", "session_cancelled", "error"
    ]
    payload: Optional[dict] = None
```

---

## Session Module

### modules/session/domain/entities/session_entity.py

```python
from dataclasses import dataclass


@dataclass
class Session:
    session_id: str
    start_time: str
    end_time: str | None
    conversation_type: str
    status: str
    current_question_index: int
    current_state: str
    retries: int
```

### modules/session/domain/interfaces/session_repository_interface.py

```python
from abc import ABC, abstractmethod


class SessionRepositoryInterface(ABC):

    @abstractmethod
    def create(self, session_id: str, conversation_type: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, session_id: str) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def update_pointer(self, session_id: str, index: int, state: str, retries: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self, session_id: str, status: str) -> None:
        raise NotImplementedError
```

### modules/session/application/use_cases/create_session.py

```python
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class CreateSession:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str, conversation_type: str) -> None:
        self._session_repository.create(session_id, conversation_type)
```

### modules/session/application/use_cases/get_session.py

```python
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class GetSession:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str) -> dict | None:
        return self._session_repository.get_by_id(session_id)
```

### modules/session/application/use_cases/update_pointer.py

```python
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class UpdatePointer:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str, index: int, state: str, retries: int) -> None:
        self._session_repository.update_pointer(session_id, index, state, retries)
```

### modules/session/application/use_cases/close_session.py

```python
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class CloseSession:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str, status: str) -> None:
        self._session_repository.close(session_id, status)
```

### modules/session/infrastructure/persistence/sqlite_session_repository.py

```python
from datetime import datetime, timezone
from app.shared.database.db import get_connection
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class SqliteSessionRepository(SessionRepositoryInterface):

    def create(self, session_id: str, conversation_type: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, start_time, conversation_type) VALUES (?, ?, ?)",
                (session_id, datetime.now(timezone.utc).isoformat(), conversation_type),
            )

    def get_by_id(self, session_id: str) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_pointer(self, session_id: str, index: int, state: str, retries: int) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET current_question_index=?, current_state=?, retries=? WHERE session_id=?",
                (index, state, retries, session_id),
            )

    def close(self, session_id: str, status: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET status=?, end_time=?, current_state='completed' WHERE session_id=?",
                (status, datetime.now(timezone.utc).isoformat(), session_id),
            )
```

---

## Message Module

### modules/message/domain/entities/message_entity.py

```python
from dataclasses import dataclass


@dataclass
class Message:
    session_id: str
    sender: str
    text: str
    timestamp: str
```

### modules/message/domain/interfaces/message_repository_interface.py

```python
from abc import ABC, abstractmethod


class MessageRepositoryInterface(ABC):

    @abstractmethod
    def add(self, session_id: str, sender: str, text: str) -> None:
        raise NotImplementedError
```

### modules/message/application/use_cases/add_message.py

```python
from app.modules.message.domain.interfaces.message_repository_interface import MessageRepositoryInterface


class AddMessage:

    def __init__(self, message_repository: MessageRepositoryInterface):
        self._message_repository = message_repository

    def execute(self, session_id: str, sender: str, text: str) -> None:
        self._message_repository.add(session_id, sender, text)
```

### modules/message/infrastructure/persistence/sqlite_message_repository.py

```python
from datetime import datetime, timezone
from app.shared.database.db import get_connection
from app.modules.message.domain.interfaces.message_repository_interface import MessageRepositoryInterface


class SqliteMessageRepository(MessageRepositoryInterface):

    def add(self, session_id: str, sender: str, text: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, sender, text, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, sender, text, datetime.now(timezone.utc).isoformat()),
            )
```

---

## Conversation Module

### modules/conversation/domain/entities/question_entity.py

```python
from dataclasses import dataclass


@dataclass
class Question:
    question_id: int
    conversation_type: str
    question_text: str
    expected_context: str
    sequence: int
```

### modules/conversation/domain/entities/response_record_entity.py

```python
from dataclasses import dataclass


@dataclass
class ResponseRecord:
    question_id: int
    session_id: str
    user_response: str
    validation_result: str
```

### modules/conversation/domain/interfaces/question_repository_interface.py

```python
from abc import ABC, abstractmethod


class QuestionRepositoryInterface(ABC):

    @abstractmethod
    def seed_questions(self, conversation_type: str, items: list[dict]) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_questions(self, conversation_type: str) -> list[dict]:
        raise NotImplementedError
```

### modules/conversation/domain/interfaces/response_repository_interface.py

```python
from abc import ABC, abstractmethod


class ResponseRepositoryInterface(ABC):

    @abstractmethod
    def add(self, question_id: int, session_id: str, user_response: str, validation_result: str) -> None:
        raise NotImplementedError
```

### modules/conversation/application/services/conversation_engine.py

```python
from app.modules.conversation.domain.interfaces.question_repository_interface import QuestionRepositoryInterface

INTRO_LINES: dict[str, str] = {
    "daily_life_companion": "I'd love to know how your day is going.",
    "career_life_advisor": "Let's talk about your career, goals, and where you'd like to go in life.",
    "health_wellness_assistant": "Let's talk about your health and how you're feeling.",
    "travel_planner": "Let's plan your next adventure.",
}

# Hardcoded scripts. AI never generates, reorders, or skips these items.
SCRIPTS: dict[str, list[dict]] = {
    "daily_life_companion": [
        {"sequence": 0, "type": "question", "text": "What should I call you?",
         "expected_context": "a name or preferred nickname"},
        {"sequence": 1, "type": "question", "text": "What time did you wake up today?",
         "expected_context": "a wake-up time"},
        {"sequence": 2, "type": "question", "text": "Did you sleep well?",
         "expected_context": "a description of sleep quality"},
        {"sequence": 3, "type": "question", "text": "What was the first thing you did this morning?",
         "expected_context": "an activity done after waking"},
        {"sequence": 4, "type": "question", "text": "Did you have breakfast?",
         "expected_context": "yes/no or a description of breakfast"},
        {"sequence": 5, "type": "question", "text": "How are you feeling right now?",
         "expected_context": "a current mood or feeling"},
        {"sequence": 6, "type": "question", "text": "How would you rate today so far?",
         "expected_context": "a rating or descriptive assessment of the day"},
        {"sequence": 7, "type": "question", "text": "What are you working on today?",
         "expected_context": "a task, project, or activity"},
        {"sequence": 8, "type": "question", "text": "What's your biggest priority?",
         "expected_context": "a stated priority or focus"},
        {"sequence": 9, "type": "question", "text": "Is anything stressing you out?",
         "expected_context": "yes/no or a source of stress"},
        {"sequence": 10, "type": "question", "text": "Have you talked to anyone interesting today?",
         "expected_context": "yes/no or a description of a conversation"},
        {"sequence": 11, "type": "question", "text": "Have you learned something new recently?",
         "expected_context": "yes/no or a new fact or skill learned"},
        {"sequence": 12, "type": "question", "text": "Did anything make you smile today?",
         "expected_context": "yes/no or a positive moment"},
        {"sequence": 13, "type": "question", "text": "Did anything frustrate you today?",
         "expected_context": "yes/no or a frustrating moment"},
        {"sequence": 14, "type": "question", "text": "How productive have you been?",
         "expected_context": "a productivity level description"},
        {"sequence": 15, "type": "question", "text": "What task have you been avoiding?",
         "expected_context": "a task being avoided"},
        {"sequence": 16, "type": "question", "text": "What's distracting you lately?",
         "expected_context": "a source of distraction"},
        {"sequence": 17, "type": "question", "text": "What's one thing you'd like to accomplish before the day ends?",
         "expected_context": "a goal for the rest of the day"},
        {"sequence": 18, "type": "question", "text": "Are you happy with how you're spending your time?",
         "expected_context": "yes/no with optional reasoning"},
        {"sequence": 19, "type": "question", "text": "If you had an extra hour today, what would you do?",
         "expected_context": "a hypothetical activity"},
        {"sequence": 20, "type": "question", "text": "What are you grateful for today?",
         "expected_context": "something the user is grateful for"},
        {"sequence": 21, "type": "question", "text": "What is something you're looking forward to?",
         "expected_context": "an upcoming event or moment"},
        {"sequence": 22, "type": "question", "text": "What's currently on your mind?",
         "expected_context": "a current thought or concern"},
        {"sequence": 23, "type": "question", "text": "Is there anything bothering you?",
         "expected_context": "yes/no or a concern"},
        {"sequence": 24, "type": "question", "text": "What's the best thing that happened this week?",
         "expected_context": "a positive event from this week"},
        {"sequence": 25, "type": "question", "text": "What's your plan for tomorrow?",
         "expected_context": "a plan or intention for tomorrow"},
        {"sequence": 26, "type": "question", "text": "What's one thing you'd like to improve about yourself?",
         "expected_context": "a personal improvement area"},
        {"sequence": 27, "type": "question", "text": "Is there someone you'd like to reconnect with?",
         "expected_context": "yes/no or a person's name or relation"},
        {"sequence": 28, "type": "question", "text": "If today had a title, what would it be?",
         "expected_context": "a short title or phrase describing the day"},
        {"sequence": 29, "type": "question", "text": "Is there anything you'd like my help with before we end?",
         "expected_context": "yes/no or a request for help"},
    ],
    "career_life_advisor": [
        {"sequence": 0, "type": "question", "text": "What should I call you?",
         "expected_context": "a name or preferred nickname"},
        {"sequence": 1, "type": "question", "text": "How old are you?",
         "expected_context": "an age"},
        {"sequence": 2, "type": "question", "text": "Where are you currently living?",
         "expected_context": "a city, region, or country"},
        {"sequence": 3, "type": "question", "text": "What do you do for a living?",
         "expected_context": "a job title or occupation"},
        {"sequence": 4, "type": "question", "text": "Are you satisfied with your current role?",
         "expected_context": "yes/no with optional reasoning"},
        {"sequence": 5, "type": "question", "text": "What is your dream job?",
         "expected_context": "a job title or career description"},
        {"sequence": 6, "type": "question", "text": "Why does it appeal to you?",
         "expected_context": "a reason or motivation"},
        {"sequence": 7, "type": "question", "text": "How many years of experience do you have?",
         "expected_context": "a number of years"},
        {"sequence": 8, "type": "question", "text": "What skills are you strongest in?",
         "expected_context": "one or more named skills"},
        {"sequence": 9, "type": "question", "text": "Which skill would you like to improve?",
         "expected_context": "a named skill"},
        {"sequence": 10, "type": "question", "text": "What's the biggest project you've worked on?",
         "expected_context": "a description of a project"},
        {"sequence": 11, "type": "question", "text": "Have you ever managed a team?",
         "expected_context": "yes/no with optional detail"},
        {"sequence": 12, "type": "question", "text": "Startup or enterprise?",
         "expected_context": "a stated preference between startup and enterprise"},
        {"sequence": 13, "type": "question", "text": "Remote or office?",
         "expected_context": "a stated preference between remote and office"},
        {"sequence": 14, "type": "question", "text": "Which companies would you love to work for?",
         "expected_context": "one or more company names"},
        {"sequence": 15, "type": "question", "text": "What are you learning right now?",
         "expected_context": "a skill or subject currently being learned"},
        {"sequence": 16, "type": "question", "text": "What is your biggest career goal?",
         "expected_context": "a stated career goal"},
        {"sequence": 17, "type": "question", "text": "What's preventing you from reaching it?",
         "expected_context": "an obstacle or barrier"},
        {"sequence": 18, "type": "question", "text": "What motivates you?",
         "expected_context": "a source of motivation"},
        {"sequence": 19, "type": "question", "text": "What usually distracts you?",
         "expected_context": "a source of distraction"},
        {"sequence": 20, "type": "question", "text": "What does success mean to you?",
         "expected_context": "a personal definition of success"},
        {"sequence": 21, "type": "question", "text": "Where do you see yourself in one year?",
         "expected_context": "a one-year outlook"},
        {"sequence": 22, "type": "question", "text": "Five years?",
         "expected_context": "a five-year outlook"},
        {"sequence": 23, "type": "question", "text": "Ten years?",
         "expected_context": "a ten-year outlook"},
        {"sequence": 24, "type": "question", "text": "Do you want financial freedom, recognition, or impact?",
         "expected_context": "a stated priority among financial freedom, recognition, or impact"},
        {"sequence": 25, "type": "question", "text": "If money weren't a factor, what would you do?",
         "expected_context": "a hypothetical career or life choice"},
        {"sequence": 26, "type": "question", "text": "What's your greatest achievement?",
         "expected_context": "a described achievement"},
        {"sequence": 27, "type": "question", "text": "What's your biggest regret?",
         "expected_context": "a described regret"},
        {"sequence": 28, "type": "question", "text": "Who inspires you?",
         "expected_context": "a person or type of person"},
        {"sequence": 29, "type": "question", "text": "What's one thing you'd tell your younger self?",
         "expected_context": "a piece of advice"},
        {"sequence": 30, "type": "question", "text": "What habit would you like to develop?",
         "expected_context": "a named habit"},
        {"sequence": 31, "type": "question", "text": "What habit would you like to eliminate?",
         "expected_context": "a named habit"},
        {"sequence": 32, "type": "question", "text": "What are you most proud of?",
         "expected_context": "a source of pride"},
        {"sequence": 33, "type": "question", "text": "What's your biggest fear about the future?",
         "expected_context": "a described fear"},
        {"sequence": 34, "type": "question", "text": "What would make you feel fulfilled?",
         "expected_context": "a description of fulfillment"},
    ],
    "health_wellness_assistant": [
        {"sequence": 0, "type": "question", "text": "What should I call you?",
         "expected_context": "a name or preferred nickname"},
        {"sequence": 1, "type": "question", "text": "How old are you?",
         "expected_context": "an age"},
        {"sequence": 2, "type": "question", "text": "What's your height?",
         "expected_context": "a height measurement"},
        {"sequence": 3, "type": "question", "text": "What's your weight?",
         "expected_context": "a weight measurement"},
        {"sequence": 4, "type": "question", "text": "What do you do for work?",
         "expected_context": "a job title or occupation"},
        {"sequence": 5, "type": "question", "text": "How would you rate your health?",
         "expected_context": "a self-rated health assessment"},
        {"sequence": 6, "type": "question", "text": "Do you have any medical conditions?",
         "expected_context": "yes/no or named condition(s)"},
        {"sequence": 7, "type": "question", "text": "Are you taking any medication?",
         "expected_context": "yes/no or named medication(s)"},
        {"sequence": 8, "type": "question", "text": "Have you had any recent symptoms?",
         "expected_context": "yes/no or described symptoms"},
        {"sequence": 9, "type": "question", "text": "When was your last medical checkup?",
         "expected_context": "a date or time period"},
        {"sequence": 10, "type": "question", "text": "How many hours do you sleep?",
         "expected_context": "a number of hours"},
        {"sequence": 11, "type": "question", "text": "Do you wake up feeling rested?",
         "expected_context": "yes/no"},
        {"sequence": 12, "type": "question", "text": "Do you use screens before bed?",
         "expected_context": "yes/no"},
        {"sequence": 13, "type": "question", "text": "Do you have trouble falling asleep?",
         "expected_context": "yes/no"},
        {"sequence": 14, "type": "question", "text": "Do you take naps?",
         "expected_context": "yes/no or a frequency"},
        {"sequence": 15, "type": "question", "text": "Do you exercise regularly?",
         "expected_context": "yes/no or a frequency"},
        {"sequence": 16, "type": "question", "text": "What type of exercise do you do?",
         "expected_context": "a named type of exercise"},
        {"sequence": 17, "type": "question", "text": "How many days a week do you work out?",
         "expected_context": "a number of days"},
        {"sequence": 18, "type": "question", "text": "What is your fitness goal?",
         "expected_context": "a stated fitness goal"},
        {"sequence": 19, "type": "question", "text": "What's stopping you from reaching it?",
         "expected_context": "an obstacle or barrier"},
        {"sequence": 20, "type": "question", "text": "How many meals do you eat daily?",
         "expected_context": "a number of meals"},
        {"sequence": 21, "type": "question", "text": "How much water do you drink?",
         "expected_context": "an amount of water"},
        {"sequence": 22, "type": "question", "text": "How often do you eat fast food?",
         "expected_context": "a frequency"},
        {"sequence": 23, "type": "question", "text": "Tea or coffee?",
         "expected_context": "a stated preference between tea and coffee"},
        {"sequence": 24, "type": "question", "text": "Do you consume sugary drinks?",
         "expected_context": "yes/no or a frequency"},
        {"sequence": 25, "type": "question", "text": "How stressed are you lately?",
         "expected_context": "a stress level description"},
        {"sequence": 26, "type": "question", "text": "What helps you relax?",
         "expected_context": "a relaxation activity"},
        {"sequence": 27, "type": "question", "text": "Do you spend enough time outdoors?",
         "expected_context": "yes/no with optional detail"},
        {"sequence": 28, "type": "question", "text": "How much time do you spend sitting?",
         "expected_context": "a duration"},
        {"sequence": 29, "type": "question", "text": "Do you have a healthy work-life balance?",
         "expected_context": "yes/no with optional reasoning"},
        {"sequence": 30, "type": "question", "text": "What's one thing you'd like to improve about your health?",
         "expected_context": "a named health improvement area"},
        {"sequence": 31, "type": "question", "text": "What healthy habit are you proud of?",
         "expected_context": "a named healthy habit"},
        {"sequence": 32, "type": "question", "text": "What's the biggest challenge in maintaining your health?",
         "expected_context": "a described challenge"},
        {"sequence": 33, "type": "question", "text": "What would an ideal day look like for you?",
         "expected_context": "a description of an ideal day"},
        {"sequence": 34, "type": "question", "text": "Is there anything health-related you'd like help with?",
         "expected_context": "yes/no or a request for help"},
    ],
    "travel_planner": [
        {"sequence": 0, "type": "question", "text": "What should I call you?",
         "expected_context": "a name or preferred nickname"},
        {"sequence": 1, "type": "question", "text": "Have you traveled recently?",
         "expected_context": "yes/no or a recent destination"},
        {"sequence": 2, "type": "question", "text": "What's your favorite destination so far?",
         "expected_context": "a destination name"},
        {"sequence": 3, "type": "question", "text": "Do you prefer domestic or international travel?",
         "expected_context": "a stated preference"},
        {"sequence": 4, "type": "question", "text": "Mountains, beaches, or cities?",
         "expected_context": "a stated preference among mountains, beaches, or cities"},
        {"sequence": 5, "type": "question", "text": "Where would you like to go next?",
         "expected_context": "a destination name"},
        {"sequence": 6, "type": "question", "text": "Why that destination?",
         "expected_context": "a reason"},
        {"sequence": 7, "type": "question", "text": "When are you planning to travel?",
         "expected_context": "a date, month, or season"},
        {"sequence": 8, "type": "question", "text": "How long will the trip be?",
         "expected_context": "a duration"},
        {"sequence": 9, "type": "question", "text": "What's your budget?",
         "expected_context": "a budget amount or range"},
        {"sequence": 10, "type": "question", "text": "Do you prefer luxury or budget travel?",
         "expected_context": "a stated preference"},
        {"sequence": 11, "type": "question", "text": "Solo, family, or friends?",
         "expected_context": "a stated travel-companion preference"},
        {"sequence": 12, "type": "question", "text": "Hotel, hostel, or Airbnb?",
         "expected_context": "a stated accommodation preference"},
        {"sequence": 13, "type": "question", "text": "Window seat or aisle seat?",
         "expected_context": "a stated seat preference"},
        {"sequence": 14, "type": "question", "text": "Early morning or late-night flights?",
         "expected_context": "a stated flight-time preference"},
        {"sequence": 15, "type": "question", "text": "Do you enjoy food tourism?",
         "expected_context": "yes/no"},
        {"sequence": 16, "type": "question", "text": "Adventure activities?",
         "expected_context": "yes/no or a named activity"},
        {"sequence": 17, "type": "question", "text": "Historical sites?",
         "expected_context": "yes/no"},
        {"sequence": 18, "type": "question", "text": "Shopping?",
         "expected_context": "yes/no"},
        {"sequence": 19, "type": "question", "text": "Nature?",
         "expected_context": "yes/no"},
        {"sequence": 20, "type": "question", "text": "What's the best trip you've ever had?",
         "expected_context": "a described trip"},
        {"sequence": 21, "type": "question", "text": "What's the worst travel experience you've had?",
         "expected_context": "a described experience"},
        {"sequence": 22, "type": "question", "text": "Have you ever missed a flight?",
         "expected_context": "yes/no with optional detail"},
        {"sequence": 23, "type": "question", "text": "Have you ever traveled alone?",
         "expected_context": "yes/no with optional detail"},
        {"sequence": 24, "type": "question", "text": "What's one country you'd love to visit?",
         "expected_context": "a country name"},
        {"sequence": 25, "type": "question", "text": "What are your must-have items when traveling?",
         "expected_context": "one or more named items"},
        {"sequence": 26, "type": "question", "text": "Do you overpack or travel light?",
         "expected_context": "a stated packing style"},
        {"sequence": 27, "type": "question", "text": "What's your ideal vacation?",
         "expected_context": "a description of an ideal vacation"},
        {"sequence": 28, "type": "question", "text": "How do you usually plan trips?",
         "expected_context": "a description of a planning approach"},
        {"sequence": 29, "type": "question", "text": "What's the first thing you do after arriving somewhere new?",
         "expected_context": "a described first activity"},
        {"sequence": 30, "type": "question", "text": "If you could travel anywhere tomorrow, where would you go?",
         "expected_context": "a destination name"},
        {"sequence": 31, "type": "question", "text": "What's on your travel bucket list?",
         "expected_context": "one or more destinations or experiences"},
        {"sequence": 32, "type": "question", "text": "What's one place you never want to visit?",
         "expected_context": "a place name"},
        {"sequence": 33, "type": "question", "text": "What would make a trip unforgettable?",
         "expected_context": "a described quality or experience"},
        {"sequence": 34, "type": "question", "text": "Would you like me to help plan your next journey?",
         "expected_context": "yes/no"},
    ],
}


class ConversationEngine:

    def __init__(self, question_repository: QuestionRepositoryInterface):
        self._question_repository = question_repository

    def load_script(self, conversation_type: str) -> list[dict]:
        items = SCRIPTS[conversation_type]
        self._question_repository.seed_questions(conversation_type, [
            {"sequence": i["sequence"], "text": i["text"], "expected_context": i["expected_context"]}
            for i in items
        ])
        return items

    def get_intro_line(self, conversation_type: str) -> str:
        return INTRO_LINES[conversation_type]

    def get_current(self, conversation_type: str, index: int) -> dict | None:
        items = SCRIPTS[conversation_type]
        return items[index] if index < len(items) else None

    def is_complete(self, conversation_type: str, index: int) -> bool:
        return index >= len(SCRIPTS[conversation_type])
```

### modules/conversation/application/use_cases/load_script.py

```python
from app.modules.conversation.application.services.conversation_engine import ConversationEngine


class LoadScript:

    def __init__(self, conversation_engine: ConversationEngine):
        self._conversation_engine = conversation_engine

    def execute(self, conversation_type: str) -> list[dict]:
        return self._conversation_engine.load_script(conversation_type)
```

### modules/conversation/application/use_cases/get_current_question.py

```python
from app.modules.conversation.application.services.conversation_engine import ConversationEngine


class GetCurrentQuestion:

    def __init__(self, conversation_engine: ConversationEngine):
        self._conversation_engine = conversation_engine

    def execute(self, conversation_type: str, index: int) -> dict | None:
        return self._conversation_engine.get_current(conversation_type, index)
```

### modules/conversation/application/use_cases/check_completion.py

```python
from app.modules.conversation.application.services.conversation_engine import ConversationEngine


class CheckCompletion:

    def __init__(self, conversation_engine: ConversationEngine):
        self._conversation_engine = conversation_engine

    def execute(self, conversation_type: str, index: int) -> bool:
        return self._conversation_engine.is_complete(conversation_type, index)
```

### modules/conversation/application/use_cases/validate_response.py

```python
import json
import litellm
from app.shared.config.settings import settings


VALIDATION_PROMPT = """You validate one turn of a scripted voice conversation.
Item type: {item_type}
Expected context: {expected_context}
User response: {user_response}

If item_type is "instruction", determine ONLY whether the user expressed completion
intent (e.g. done, finished, yes, ready). Do not judge whether the action occurred.
If item_type is "question", determine ONLY whether the response is topically relevant
to the expected context. Do not judge factual correctness.

Respond with strict JSON only: {{"valid": true|false, "reason": "<short reason>"}}"""


class ValidateResponse:

    async def execute(self, item_type: str, expected_context: str, user_response: str) -> dict:
        prompt = VALIDATION_PROMPT.format(
            item_type=item_type, expected_context=expected_context, user_response=user_response
        )
        try:
            response = await litellm.acompletion(
                model=settings.ai_validation_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
            )
            text = response.choices[0].message.content
            return json.loads(text)
        except Exception:
            return {"valid": False, "reason": "validation_unavailable"}
```


### modules/conversation/application/use_cases/record_response.py

```python
from app.modules.conversation.domain.interfaces.response_repository_interface import ResponseRepositoryInterface


class RecordResponse:

    def __init__(self, response_repository: ResponseRepositoryInterface):
        self._response_repository = response_repository

    def execute(self, question_id: int, session_id: str, user_response: str, validation_result: str) -> None:
        self._response_repository.add(question_id, session_id, user_response, validation_result)
```

### modules/conversation/infrastructure/persistence/sqlite_question_repository.py

```python
from app.shared.database.db import get_connection
from app.modules.conversation.domain.interfaces.question_repository_interface import QuestionRepositoryInterface


class SqliteQuestionRepository(QuestionRepositoryInterface):

    def seed_questions(self, conversation_type: str, items: list[dict]) -> None:
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) c FROM questions WHERE conversation_type=?", (conversation_type,)
            ).fetchone()["c"]
            if existing:
                return
            for item in items:
                conn.execute(
                    "INSERT INTO questions (conversation_type, question_text, expected_context, sequence) VALUES (?, ?, ?, ?)",
                    (conversation_type, item["text"], item["expected_context"], item["sequence"]),
                )

    def get_questions(self, conversation_type: str) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM questions WHERE conversation_type=? ORDER BY sequence ASC",
                (conversation_type,),
            ).fetchall()
            return [dict(r) for r in rows]
```

### modules/conversation/infrastructure/persistence/sqlite_response_repository.py

```python
from app.shared.database.db import get_connection
from app.modules.conversation.domain.interfaces.response_repository_interface import ResponseRepositoryInterface


class SqliteResponseRepository(ResponseRepositoryInterface):

    def add(self, question_id: int, session_id: str, user_response: str, validation_result: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO responses (question_id, session_id, user_response, validation_result) VALUES (?, ?, ?, ?)",
                (question_id, session_id, user_response, validation_result),
            )
```

### modules/conversation/infrastructure/external/litellm_validation_adapter.py

```python
import json
import litellm
from app.shared.config.settings import settings

VALIDATION_PROMPT = """You validate one turn of a scripted voice conversation.
Item type: {item_type}
Expected context: {expected_context}
User response: {user_response}

If item_type is "instruction", determine ONLY whether the user expressed completion
intent (e.g. done, finished, yes, ready). Do not judge whether the action occurred.
If item_type is "question", determine ONLY whether the response is topically relevant
to the expected context. Do not judge factual correctness.

Respond with strict JSON only: {{"valid": true|false, "reason": "<short reason>"}}"""


class LiteLLMValidationAdapter:

    async def validate(self, item_type: str, expected_context: str, user_response: str) -> dict:
        prompt = VALIDATION_PROMPT.format(
            item_type=item_type, expected_context=expected_context, user_response=user_response
        )
        try:
            response = await litellm.acompletion(
                model=settings.ai_validation_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
            )
            text = response.choices[0].message.content
            return json.loads(text)
        except Exception:
            return {"valid": False, "reason": "validation_unavailable"}
```


---

## Voice Module

### modules/voice/domain/interfaces/stt_provider_interface.py

```python
from abc import ABC, abstractmethod


class STTProviderInterface(ABC):

    @abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_audio(self, chunk: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    async def receive_transcript(self) -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
```

### modules/voice/domain/interfaces/tts_provider_interface.py

```python
from abc import ABC, abstractmethod


class TTSProviderInterface(ABC):

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        raise NotImplementedError
```

### modules/voice/infrastructure/external/deepgram_stt_adapter.py

```python
import json
import websockets
from app.shared.config.settings import settings
from app.modules.voice.domain.interfaces.stt_provider_interface import STTProviderInterface

DEEPGRAM_STT_URL = "wss://api.deepgram.com/v1/listen?punctuate=true&interim_results=false"


class DeepgramSTTAdapter(STTProviderInterface):

    def __init__(self):
        self._ws = None

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            DEEPGRAM_STT_URL,
            extra_headers={"Authorization": f"Token {settings.deepgram_api_key}"},
        )

    async def send_audio(self, chunk: bytes) -> None:
        await self._ws.send(chunk)

    async def receive_transcript(self) -> str | None:
        message = await self._ws.recv()
        data = json.loads(message)
        alt = data.get("channel", {}).get("alternatives", [{}])[0]
        transcript = alt.get("transcript", "")
        return transcript if data.get("is_final") and transcript else None

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
```

### modules/voice/infrastructure/external/deepgram_tts_adapter.py

```python
import httpx
from app.shared.config.settings import settings
from app.modules.voice.domain.interfaces.tts_provider_interface import TTSProviderInterface

DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak?model=aura-asteria-en"


class DeepgramTTSAdapter(TTSProviderInterface):

    async def synthesize(self, text: str) -> bytes:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                DEEPGRAM_TTS_URL,
                headers={
                    "Authorization": f"Token {settings.deepgram_api_key}",
                    "Content-Type": "application/json",
                },
                json={"text": text},
            )
            resp.raise_for_status()
            return resp.content
```

### modules/voice/application/use_cases/synthesize_speech.py

```python
from app.modules.voice.domain.interfaces.tts_provider_interface import TTSProviderInterface


class SynthesizeSpeech:

    def __init__(self, tts_provider: TTSProviderInterface):
        self._tts_provider = tts_provider

    async def execute(self, text: str) -> bytes:
        return await self._tts_provider.synthesize(text)
```

### modules/voice/application/use_cases/stream_speech_to_text.py

```python
from app.modules.voice.domain.interfaces.stt_provider_interface import STTProviderInterface


class StreamSpeechToText:

    def __init__(self, stt_provider: STTProviderInterface):
        self._stt_provider = stt_provider

    async def connect(self) -> None:
        await self._stt_provider.connect()

    async def send_audio(self, chunk: bytes) -> None:
        await self._stt_provider.send_audio(chunk)

    async def receive_transcript(self) -> str | None:
        return await self._stt_provider.receive_transcript()

    async def close(self) -> None:
        await self._stt_provider.close()
```

---

## Interruption Module

### modules/interruption/domain/entities/interruption_entity.py

```python
from dataclasses import dataclass


@dataclass
class Interruption:
    session_id: str
    interruption_type: str
    interruption_text: str
    timestamp: str
```

### modules/interruption/domain/interfaces/interruption_repository_interface.py

```python
from abc import ABC, abstractmethod


class InterruptionRepositoryInterface(ABC):

    @abstractmethod
    def add(self, session_id: str, interruption_type: str, interruption_text: str) -> None:
        raise NotImplementedError
```

### modules/interruption/application/use_cases/classify_interruption.py

```python
STOP_PATTERNS = {"stop", "wait", "hold on"}
CANCEL_PATTERNS = {"cancel", "end session", "quit"}
REPEAT_PATTERNS = {"repeat", "say that again", "come again"}
CORRECTION_MARKERS = {"no,", "actually,", "i meant", "correction"}


class ClassifyInterruption:

    def execute(self, transcript: str) -> str | None:
        t = transcript.strip().lower()
        if t in STOP_PATTERNS:
            return "stop"
        if t in CANCEL_PATTERNS:
            return "cancel"
        if t in REPEAT_PATTERNS:
            return "repeat"
        if any(t.startswith(marker) for marker in CORRECTION_MARKERS):
            return "correction"
        return None
```

### modules/interruption/application/use_cases/record_interruption.py

```python
from app.modules.interruption.domain.interfaces.interruption_repository_interface import InterruptionRepositoryInterface


class RecordInterruption:

    def __init__(self, interruption_repository: InterruptionRepositoryInterface):
        self._interruption_repository = interruption_repository

    def execute(self, session_id: str, interruption_type: str, interruption_text: str) -> None:
        self._interruption_repository.add(session_id, interruption_type, interruption_text)
```

### modules/interruption/infrastructure/persistence/sqlite_interruption_repository.py

```python
from datetime import datetime, timezone
from app.shared.database.db import get_connection
from app.modules.interruption.domain.interfaces.interruption_repository_interface import InterruptionRepositoryInterface


class SqliteInterruptionRepository(InterruptionRepositoryInterface):

    def add(self, session_id: str, interruption_type: str, interruption_text: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO interruptions (session_id, interruption_type, interruption_text, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, interruption_type, interruption_text, datetime.now(timezone.utc).isoformat()),
            )
```

---

## Entrypoints (Presentation Layer)

### entrypoints/websocket/connection_manager.py

```python
from fastapi import WebSocket


class ConnectionManager:

    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self.active[session_id] = ws

    def disconnect(self, session_id: str):
        self.active.pop(session_id, None)

    async def send_json(self, session_id: str, payload: dict):
        ws = self.active.get(session_id)
        if ws:
            await ws.send_json(payload)

    async def send_bytes(self, session_id: str, data: bytes):
        ws = self.active.get(session_id)
        if ws:
            await ws.send_bytes(data)


manager = ConnectionManager()
```

### entrypoints/response_formatter.py

```python
def event(event_name: str, payload: dict | None = None) -> dict:
    return {"event": event_name, "payload": payload or {}}


def question_event(item: dict) -> dict:
    return event("question" if item["type"] == "question" else "instruction", {
        "text": item["text"], "sequence": item["sequence"],
    })


def validation_event(valid: bool, reason: str) -> dict:
    return event("validation_result", {"valid": valid, "reason": reason})


def completed_event() -> dict:
    return event("session_completed")


def cancelled_event() -> dict:
    return event("session_cancelled")


def error_event(message: str) -> dict:
    return event("error", {"message": message})
```

### entrypoints/http/health.py

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}
```

### entrypoints/websocket/conversation_handler.py

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.entrypoints.websocket.connection_manager import manager
from app.entrypoints import response_formatter as fmt
from app.shared.config.settings import settings

# Infrastructure adapters (concrete implementations)
from app.modules.session.infrastructure.persistence.sqlite_session_repository import SqliteSessionRepository
from app.modules.message.infrastructure.persistence.sqlite_message_repository import SqliteMessageRepository
from app.modules.conversation.infrastructure.persistence.sqlite_question_repository import SqliteQuestionRepository
from app.modules.conversation.infrastructure.persistence.sqlite_response_repository import SqliteResponseRepository
from app.modules.interruption.infrastructure.persistence.sqlite_interruption_repository import SqliteInterruptionRepository
from app.modules.voice.infrastructure.external.deepgram_stt_adapter import DeepgramSTTAdapter
from app.modules.voice.infrastructure.external.deepgram_tts_adapter import DeepgramTTSAdapter

# Application use cases
from app.modules.session.application.use_cases.create_session import CreateSession
from app.modules.session.application.use_cases.get_session import GetSession
from app.modules.session.application.use_cases.update_pointer import UpdatePointer
from app.modules.session.application.use_cases.close_session import CloseSession
from app.modules.message.application.use_cases.add_message import AddMessage
from app.modules.conversation.application.services.conversation_engine import ConversationEngine
from app.modules.conversation.application.use_cases.validate_response import ValidateResponse
from app.modules.conversation.application.use_cases.record_response import RecordResponse
from app.modules.interruption.application.use_cases.classify_interruption import ClassifyInterruption
from app.modules.interruption.application.use_cases.record_interruption import RecordInterruption
from app.modules.voice.application.use_cases.synthesize_speech import SynthesizeSpeech

router = APIRouter()


@router.websocket("/ws/{conversation_type}/{session_id}")
async def conversation_socket(ws: WebSocket, conversation_type: str, session_id: str):
    # --- Dependency Injection: wire adapters into use cases ---
    session_repo = SqliteSessionRepository()
    message_repo = SqliteMessageRepository()
    question_repo = SqliteQuestionRepository()
    response_repo = SqliteResponseRepository()
    interruption_repo = SqliteInterruptionRepository()
    tts_adapter = DeepgramTTSAdapter()
    stt_adapter = DeepgramSTTAdapter()

    create_session = CreateSession(session_repo)
    get_session = GetSession(session_repo)
    update_pointer = UpdatePointer(session_repo)
    close_session = CloseSession(session_repo)
    add_message = AddMessage(message_repo)
    conversation_engine = ConversationEngine(question_repo)
    validate_response = ValidateResponse()
    record_response = RecordResponse(response_repo)
    classify_interruption = ClassifyInterruption()
    record_interruption = RecordInterruption(interruption_repo)
    synthesize_speech = SynthesizeSpeech(tts_adapter)

    # --- Connection setup ---
    await manager.connect(session_id, ws)

    session = get_session.execute(session_id)
    if not session:
        create_session.execute(session_id, conversation_type)
        conversation_engine.load_script(conversation_type)
        index, retries = 0, 0
    else:
        index, retries = session["current_question_index"], session["retries"]

    await stt_adapter.connect()

    # --- Helper: speak text via TTS ---
    async def speak(text: str):
        add_message.execute(session_id, "system", text)
        audio = await synthesize_speech.execute(text)
        await manager.send_json(session_id, fmt.event("tts_audio_meta", {"text": text}))
        await manager.send_bytes(session_id, audio)

    # --- Helper: ask current question ---
    async def ask_current():
        nonlocal index
        item = conversation_engine.get_current(conversation_type, index)
        if item is None:
            close_session.execute(session_id, "completed")
            await manager.send_json(session_id, fmt.completed_event())
            await ws.close()
            return False
        await manager.send_json(session_id, fmt.question_event(item))
        await speak(item["text"])
        return True

    # --- Session start ---
    await manager.send_json(session_id, fmt.event("session_started", {"session_id": session_id}))
    await speak(conversation_engine.get_intro_line(conversation_type))
    if not await ask_current():
        return

    # --- Main conversation loop ---
    try:
        while True:
            frame = await ws.receive()
            if "bytes" in frame and frame["bytes"] is not None:
                await stt_adapter.send_audio(frame["bytes"])
                continue

            transcript = await stt_adapter.receive_transcript()
            if not transcript:
                continue

            add_message.execute(session_id, "user", transcript)

            interruption = classify_interruption.execute(transcript)
            if interruption == "stop":
                record_interruption.execute(session_id, "stop", transcript)
                await manager.send_json(session_id, fmt.event("tts_stop"))
                continue
            if interruption == "cancel":
                record_interruption.execute(session_id, "cancel", transcript)
                close_session.execute(session_id, "cancelled")
                await manager.send_json(session_id, fmt.cancelled_event())
                await ws.close()
                break
            if interruption == "repeat":
                record_interruption.execute(session_id, "repeat", transcript)
                await ask_current()
                continue
            if interruption == "correction":
                record_interruption.execute(session_id, "correction", transcript)
                # operative text is this transcript itself; fall through to validation

            item = conversation_engine.get_current(conversation_type, index)
            result = await validate_response.execute(item["type"], item["expected_context"], transcript)
            record_response.execute(
                item["sequence"], session_id, transcript, "valid" if result["valid"] else "invalid"
            )
            await manager.send_json(session_id, fmt.validation_event(result["valid"], result["reason"]))

            if result["valid"]:
                index += 1
                retries = 0
                update_pointer.execute(session_id, index, "asking", retries)
                if not await ask_current():
                    break
            else:
                retries += 1
                update_pointer.execute(session_id, index, "repeating", retries)
                if retries >= settings.max_retries_per_item:
                    await speak("Let's move on for now.")
                    index += 1
                    retries = 0
                    update_pointer.execute(session_id, index, "asking", retries)
                    if not await ask_current():
                        break
                else:
                    await speak(result["reason"])
                    await ask_current()

    except WebSocketDisconnect:
        pass
    finally:
        await stt_adapter.close()
        manager.disconnect(session_id)
```

---

## Application Entrypoint

### main.py

```python
from fastapi import FastAPI
from app.entrypoints.websocket.conversation_handler import router as ws_router
from app.entrypoints.http.health import router as health_router
from app.shared.database.init_db import init_db

app = FastAPI(title="Conversational Widget Backend")


@app.on_event("startup")
async def on_startup():
    init_db()


app.include_router(health_router)
app.include_router(ws_router)
```

---

## Live Transcript Overlay — Backend Addendum

### Minimal change to `entrypoints/websocket/conversation_handler.py`

The only backend change is emitting `user_partial_transcript` events for
non-final Deepgram STT results. This requires modifying `DeepgramSTTAdapter`
to expose a raw receive method for non-final frames, and updating the
receive loop in `conversation_handler.py`.

#### Change 1: `modules/voice/infrastructure/external/deepgram_stt_adapter.py`

Add a `receive_any` method alongside the existing `receive_transcript`:

```python
async def receive_any(self) -> dict:
    """Return the raw parsed Deepgram message — caller decides final vs partial."""
    message = await self._ws.recv()
    return json.loads(message)
```

The existing `receive_transcript` (which returns only `is_final` results) is
unchanged and still used for the validation path. `receive_any` is only
called by the updated receive loop below.

#### Change 2: `entrypoints/websocket/conversation_handler.py` — receive loop

Replace the existing inner receive loop (the `frame = await ws.receive()` block)
with the version below. All existing logic is identical; the only addition is
the two lines that emit `user_partial_transcript` for non-final Deepgram frames.

```python
    # --- Main conversation loop (transcript-aware version) ---
    try:
        while True:
            frame = await ws.receive()
            if "bytes" in frame and frame["bytes"] is not None:
                await stt_adapter.send_audio(frame["bytes"])

                # Check for any Deepgram result (partial OR final)
                raw = await stt_adapter.receive_any()
                alt = raw.get("channel", {}).get("alternatives", [{}])[0]
                text = alt.get("transcript", "")
                is_final = raw.get("is_final", False)

                if text and not is_final:
                    # Emit partial — frontend displays transiently, never persisted
                    await manager.send_json(
                        session_id, fmt.event("user_partial_transcript", {"text": text})
                    )
                    continue

                if not is_final or not text:
                    continue

                transcript = text  # finalized

            else:
                continue

            # ── everything below is IDENTICAL to the existing handler ──

            add_message.execute(session_id, "user", transcript)

            interruption = classify_interruption.execute(transcript)
            if interruption == "stop":
                record_interruption.execute(session_id, "stop", transcript)
                await manager.send_json(session_id, fmt.event("tts_stop"))
                continue
            if interruption == "cancel":
                record_interruption.execute(session_id, "cancel", transcript)
                close_session.execute(session_id, "cancelled")
                await manager.send_json(session_id, fmt.cancelled_event())
                await ws.close()
                break
            if interruption == "repeat":
                record_interruption.execute(session_id, "repeat", transcript)
                await ask_current()
                continue
            if interruption == "correction":
                record_interruption.execute(session_id, "correction", transcript)

            item = conversation_engine.get_current(conversation_type, index)
            result = await validate_response.execute(item["type"], item["expected_context"], transcript)
            record_response.execute(
                item["sequence"], session_id, transcript, "valid" if result["valid"] else "invalid"
            )
            await manager.send_json(session_id, fmt.validation_event(result["valid"], result["reason"]))

            if result["valid"]:
                index += 1
                retries = 0
                update_pointer.execute(session_id, index, "asking", retries)
                if not await ask_current():
                    break
            else:
                retries += 1
                update_pointer.execute(session_id, index, "repeating", retries)
                if retries >= settings.max_retries_per_item:
                    await speak("Let's move on for now.")
                    index += 1
                    retries = 0
                    update_pointer.execute(session_id, index, "asking", retries)
                    if not await ask_current():
                        break
                else:
                    await speak(result["reason"])
                    await ask_current()

    except WebSocketDisconnect:
        pass
    finally:
        await stt_adapter.close()
        manager.disconnect(session_id)
```

**What changed vs the original handler:**
- Added `receive_any()` call to inspect the raw Deepgram message.
- If `is_final=False` and text is non-empty → emit `user_partial_transcript`, `continue`.
- If `is_final=True` → extract final text and fall through to existing logic (unchanged).
- All session management, pointer updates, interruptions, validation, retry logic: **identical**.

**What did not change:**
- No new modules, no new use cases, no new repository methods.
- No SQLite schema changes — partial transcripts are never written to the DB.
- The `messages` table continues to receive only finalized assistant and user text via `add_message.execute(...)`.

