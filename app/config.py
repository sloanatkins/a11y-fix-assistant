"""
Settings
========
Loads the settings we keep in .env.

Dependencies:
    - python-dotenv
"""

import os

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"
