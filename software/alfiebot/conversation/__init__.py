"""Conversation and intent engine.

- ``intents.py``: deterministic phrase matching ("how are you", "what can
  you do", ...), the typed wake phrase, and a fallback for anything else.
- ``responses.json``: several alternative replies per intent, plus the
  face to show while saying them. Edit this file to change what AlfieBot says.
- ``engine.py``: picks the intent and reply and says what to do next.
"""
