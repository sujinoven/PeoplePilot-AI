import os
from pathlib import Path

from dotenv import load_dotenv

# Load variables from the local .env file (see .env.example).
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- LangSmith ------------------------------------------------------------
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "default")

# --- Models ---------------------------------------------------------------
# gpt-4.1-mini with temperature 0 keeps HR answers consistent and factual.
LLM_MODEL = "gpt-4.1-mini"
TEMPERATURE = 0

# text-embedding-3-small is sufficient for a 57-page HR handbook.
EMBEDDING_MODEL = "text-embedding-3-small"

# --- RAG settings ---------------------------------------------------------
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
RETRIEVER_K = 4

# --- Paths ----------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
HANDBOOK_PATH = DATA_DIR / "PROITBRIDGE_Employee_Handbook_2026_1.pdf"


def check_config() -> None:
    """Fail early with a clear message if a key or the handbook is missing."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")
    if LANGSMITH_TRACING and not LANGSMITH_API_KEY:
        raise RuntimeError(
            "LANGSMITH_TRACING is true but LANGSMITH_API_KEY is not set. "
            "Add the key to your .env file."
        )
    if not HANDBOOK_PATH.exists():
        raise FileNotFoundError(
            f"Employee Handbook not found at: {HANDBOOK_PATH}\n"
            "Place PROITBRIDGE_Employee_Handbook_2026_1.pdf inside the data/ folder."
        )
