"""Conversation and intent engine (Stage 2).

Planned layout:

- ``intents.py``: deterministic phrase matching ("how are you", "what can
  you do", ...) with a fallback intent for anything unsupported.
- ``responses.json``: several alternative replies per intent.
- ``engine.py``: takes recognised text, picks the intent, chooses a reply
  and tells the robot which state and expression to show.

Stage 1 only records typed text in the transcript.
"""
