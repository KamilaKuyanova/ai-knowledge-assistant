from tests.conftest import register

VACATION = (
    "Порядок оформления отпуска.\n"
    "Сотрудник подаёт заявление на отпуск руководителю не позднее чем за 14 календарных дней. "
    "Отпуск оформляется через портал кадровых заявлений."
)
EXPENSES = "Возмещение командировочных расходов происходит в течение десяти рабочих дней после авансового отчёта."


def upload(client, auth, name, text):
    r = client.post("/api/documents", headers=auth, files={"file": (name, text.encode(), "text/plain")})
    assert r.status_code == 202, r.text
    return r.json()


def new_chat(client, auth):
    return client.post("/api/chats", headers=auth).json()["id"]


def test_auth_flow_and_duplicate_email(client):
    h = register(client)
    assert client.get("/api/auth/me", headers=h).json()["email"] == "a@example.com"
    assert client.post("/api/auth/register", json={"email": "A@example.com", "password": "password123"}).status_code == 409
    ok = client.post("/api/auth/login", data={"username": "a@example.com", "password": "password123"})
    assert ok.status_code == 200
    bad = client.post("/api/auth/login", data={"username": "a@example.com", "password": "wrong-password"})
    assert bad.status_code == 401


def test_endpoints_require_auth(client):
    for path in ("/api/documents", "/api/chats", "/api/auth/me"):
        assert client.get(path).status_code == 401


def test_upload_is_indexed_and_listed(client, auth):
    doc = upload(client, auth, "vacation.txt", VACATION)
    got = client.get(f"/api/documents/{doc['id']}", headers=auth).json()
    assert got["status"] == "ready" and got["chunk_count"] >= 1


def test_upload_rejects_bad_type_and_empty(client, auth):
    r = client.post("/api/documents", headers=auth, files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415
    r = client.post("/api/documents", headers=auth, files={"file": ("x.txt", b"", "text/plain")})
    assert r.status_code == 400


def test_unreadable_file_marked_failed(client, auth):
    r = client.post("/api/documents", headers=auth, files={"file": ("bad.pdf", b"not a pdf", "application/pdf")})
    doc = client.get(f"/api/documents/{r.json()['id']}", headers=auth).json()
    assert doc["status"] == "failed" and doc["error"]


def test_answer_has_sources_with_quote(client, auth, llm):
    upload(client, auth, "vacation.txt", VACATION)
    upload(client, auth, "expenses.txt", EXPENSES)
    chat = new_chat(client, auth)
    r = client.post(f"/api/chats/{chat}/ask", headers=auth, json={"question": "За сколько дней подать заявление на отпуск?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answered"] is True
    assert body["sources"][0]["filename"] == "vacation.txt"
    assert "14 календарных дней" in body["sources"][0]["quote"]
    assert "[1]" in llm.calls[0][-1]["content"]  # контекст реально ушёл в промпт


def test_irrelevant_question_refused_without_calling_llm(client, auth, llm):
    upload(client, auth, "vacation.txt", VACATION)
    chat = new_chat(client, auth)
    r = client.post(f"/api/chats/{chat}/ask", headers=auth, json={"question": "Какая столица Австралии?"})
    body = r.json()
    assert body["answered"] is False and body["sources"] == []
    assert llm.calls == []


def test_model_no_answer_marker_becomes_refusal(client, auth, llm):
    upload(client, auth, "vacation.txt", VACATION)
    llm.reply = "NO_ANSWER"
    chat = new_chat(client, auth)
    r = client.post(f"/api/chats/{chat}/ask", headers=auth, json={"question": "Сколько дней отпуска положено?"})
    assert r.json()["answered"] is False and r.json()["sources"] == []


def test_history_saved_and_title_set(client, auth):
    upload(client, auth, "vacation.txt", VACATION)
    chat = new_chat(client, auth)
    client.post(f"/api/chats/{chat}/ask", headers=auth, json={"question": "Как оформить отпуск?"})
    msgs = client.get(f"/api/chats/{chat}/messages", headers=auth).json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert client.get("/api/chats", headers=auth).json()[0]["title"] == "Как оформить отпуск?"


def test_users_cannot_see_each_others_data(client, auth, llm):
    upload(client, auth, "vacation.txt", VACATION)
    chat = new_chat(client, auth)
    other = register(client, "b@example.com")

    assert client.get("/api/documents", headers=other).json() == []
    doc_id = client.get("/api/documents", headers=auth).json()[0]["id"]
    assert client.get(f"/api/documents/{doc_id}", headers=other).status_code == 404
    assert client.delete(f"/api/documents/{doc_id}", headers=other).status_code == 404
    assert client.get(f"/api/chats/{chat}/messages", headers=other).status_code == 404

    other_chat = new_chat(client, other)
    r = client.post(f"/api/chats/{other_chat}/ask", headers=other, json={"question": "Как оформить отпуск?"})
    assert r.json()["answered"] is False  # чужие документы не находятся
    assert llm.calls == []


def test_delete_document_removes_it_from_search(client, auth, llm):
    doc = upload(client, auth, "vacation.txt", VACATION)
    assert client.delete(f"/api/documents/{doc['id']}", headers=auth).status_code == 204
    chat = new_chat(client, auth)
    r = client.post(f"/api/chats/{chat}/ask", headers=auth, json={"question": "Как оформить отпуск?"})
    assert r.json()["answered"] is False


def test_user_settings_change_threshold(client, auth, llm):
    upload(client, auth, "vacation.txt", VACATION)
    chat = new_chat(client, auth)
    client.put("/api/auth/settings", headers=auth, json={"top_k": 3, "min_score": 0.99})
    r = client.post(f"/api/chats/{chat}/ask", headers=auth, json={"question": "Как оформить отпуск?"})
    assert r.json()["answered"] is False


def test_llm_failure_returns_502_and_saves_nothing(client, auth, llm):
    from app.services.llm import LLMError

    def boom(messages):
        raise LLMError("Превышен лимит бесплатного API.")

    llm.complete = boom
    upload(client, auth, "vacation.txt", VACATION)
    chat = new_chat(client, auth)
    r = client.post(f"/api/chats/{chat}/ask", headers=auth, json={"question": "Как оформить отпуск?"})
    assert r.status_code == 502 and "лимит" in r.json()["detail"]
    assert client.get(f"/api/chats/{chat}/messages", headers=auth).json() == []
