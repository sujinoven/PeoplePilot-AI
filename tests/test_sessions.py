from src.sessions import SessionStore


def make_store(max_sessions=200):
    created = []

    def factory():
        obj = object()
        created.append(obj)
        return obj

    return SessionStore(factory, max_sessions), created


def test_same_session_gets_the_same_assistant():
    store, created = make_store()
    assert store.get("a") is store.get("a")
    assert len(created) == 1


def test_different_sessions_get_different_assistants():
    store, _ = make_store()
    assert store.get("a") is not store.get("b")


def test_oldest_session_is_dropped_at_the_cap():
    store, _ = make_store(max_sessions=2)
    first = store.get("a")
    store.get("b")
    store.get("c")
    assert len(store) == 2
    assert store.get("a") is not first  # "a" was dropped, so it starts fresh


def test_using_a_session_keeps_it_alive():
    store, _ = make_store(max_sessions=2)
    a = store.get("a")
    store.get("b")
    store.get("a")  # touching "a" makes "b" the oldest
    store.get("c")
    assert store.get("a") is a