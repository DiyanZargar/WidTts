from typing import Optional, Dict, Any


def event(event_name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"event": event_name, "payload": payload or {}}


def question_event(item: Dict[str, Any]) -> Dict[str, Any]:
    return event("question" if item.get("type") == "question" else "instruction", {
        "text": item["text"], "sequence": item["sequence"],
    })


def validation_event(valid: bool, reason: str) -> Dict[str, Any]:
    return event("validation_result", {"valid": valid, "reason": reason})


def completed_event() -> Dict[str, Any]:
    return event("session_completed")


def cancelled_event() -> Dict[str, Any]:
    return event("session_cancelled")


def error_event(message: str) -> Dict[str, Any]:
    return event("error", {"message": message})
