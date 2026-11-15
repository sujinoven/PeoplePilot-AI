from collections import OrderedDict
from threading import Lock


class SessionStore:
    """One assistant per browser session. The least recently used session is dropped at the cap."""

    def __init__(self, factory, max_sessions: int = 200) -> None:
        self._factory = factory
        self._max = max_sessions
        self._sessions: OrderedDict = OrderedDict()
        self._lock = Lock()

    def get(self, session_id: str):
        with self._lock:
            if session_id in self._sessions:
                self._sessions.move_to_end(session_id)
                return self._sessions[session_id]
            assistant = self._factory()
            self._sessions[session_id] = assistant
            while len(self._sessions) > self._max:
                self._sessions.popitem(last=False)
            return assistant

    def __len__(self) -> int:
        return len(self._sessions)