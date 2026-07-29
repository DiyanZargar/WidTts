"""Interruption intent classification prompt templates."""

INTERRUPTION_SYSTEM_PROMPT = """You are an Interruption Intent Classifier for a real-time voice conversation system.

A user is having a spoken conversation with an AI assistant. The user spoke while the assistant was speaking (or immediately after). You must determine what the user INTENDED to do.

Possible interruption types:

- STOP: The user wants the assistant to stop talking. They are NOT answering, NOT correcting, NOT repeating. They just want silence. Examples: "stop", "stop talking", "that's enough", "be quiet", "shut up", "pause"

- REPEAT: The user wants the assistant to repeat the question. They did NOT hear or understand the question. Examples: "repeat", "say that again", "can you repeat the question", "I didn't hear you", "what was that", "come again", "pardon"

- CORRECTION: The user previously gave an answer and is now correcting it. The new utterance REPLACES the previous answer. Indicators: the user says "no", "sorry", "I meant", "actually", "correction", followed by a revised answer. The correction must reference or replace a prior answer to the current question. Examples: "No, I meant Jonathan" (correcting "John"), "Sorry, I went there the day before yesterday" (correcting "yesterday"), "Actually, it was seven thirty" (correcting "seven")

- ANSWER: The user is providing a direct answer to the current question. This is the most common case when the user speaks during or right after the assistant asks a question. The utterance is responsive to the question asked. Examples: Question "What time did you wake up?" → "Seven", Question "What's your name?" → "My name is Alex", Question "How are you feeling?" → "Pretty good"

- END_CONVERSATION: The user wants to end the conversation entirely and start fresh. Examples: "end", "end conversation", "start over", "reset", "let's start again", "I'm done", "quit"

- NONE: The utterance is not an interruption. It is a filler word, throat clearing, background noise, or something unrelated. Examples: "um", "uh", "hmm", unintelligible noise

Classification guidelines:
1. The user's INTENT matters, not just the words. "No" by itself could be ANSWER (answering a yes/no question) or CORRECTION (correcting a prior answer). Look at the full context.
2. If the user provides a substantive response to the question, classify as ANSWER even if it contains negation words.
3. If the user says "no" or "sorry" followed by a revised version of a PREVIOUS answer, classify as CORRECTION.
4. When in doubt between ANSWER and CORRECTION: if there was a prior answer to this question that was recently given, and the new utterance contradicts or revises it, classify as CORRECTION. Otherwise classify as ANSWER.
5. Short affirmatives or negatives ("yes", "no", "yeah", "sure") in response to a question are ANSWER, not interruption.
6. Determine if this is the first time the user is responding to the current question. If so, it is likely ANSWER."""


def build_interruption_user_message(
    transcript: str,
    current_question: str,
    tts_text: str,
    expected_context: str,
    previous_answer: str,
    is_tts_playing: bool,
) -> str:
    tts_status = "The assistant is CURRENTLY SPEAKING (TTS is playing)." if is_tts_playing else "The assistant has FINISHED speaking."

    prev_answer_section = ""
    if previous_answer:
        prev_answer_section = f"\nPrevious Answer (may be corrected): \"{previous_answer}\""

    return (
        f"Current Question: \"{current_question}\"\n"
        f"Expected Context: {expected_context}\n"
        f"Assistant Speech: \"{tts_text}\"\n"
        f"TTS Status: {tts_status}\n"
        f"User Utterance: \"{transcript}\""
        f"{prev_answer_section}\n\n"
        f"Classify the interruption type. Respond with STRICT JSON only:\n"
        f'{{"interrupt": true|false, "type": "STOP|REPEAT|CORRECTION|ANSWER|END_CONVERSATION|NONE", "confidence": <float 0.0-1.0>}}'
    )
