import { useCallback, useEffect, useState } from "react";
import { api, getToken, setToken, setUnauthorizedHandler, type Chat, type User } from "./api";
import ChatView from "./components/ChatView";
import DocumentsView from "./components/DocumentsView";
import LoginForm from "./components/LoginForm";
import SettingsView from "./components/SettingsView";

type View = "chat" | "documents" | "settings";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(!!getToken());

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    if (!getToken()) return;
    api
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setChecking(false));
  }, [logout]);

  if (checking) return <div className="center muted">Загрузка…</div>;
  if (!user) {
    return (
      <LoginForm
        onAuthed={async (token) => {
          setToken(token);
          setUser(await api.me());
        }}
      />
    );
  }
  return <Workspace user={user} onUser={setUser} onLogout={logout} />;
}

function Workspace({ user, onUser, onLogout }: { user: User; onUser: (u: User) => void; onLogout: () => void }) {
  const [view, setView] = useState<View>("chat");
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);

  const reloadChats = useCallback(async () => setChats(await api.chats()), []);

  useEffect(() => {
    reloadChats().catch(() => {});
  }, [reloadChats]);

  async function newChat() {
    const chat = await api.createChat();
    await reloadChats();
    setActiveId(chat.id);
    setView("chat");
  }

  async function removeChat(id: number) {
    if (!confirm("Удалить этот чат?")) return;
    await api.deleteChat(id);
    if (activeId === id) setActiveId(null);
    await reloadChats();
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>Knowledge Assistant</h1>
        <button className="primary" onClick={newChat}>
          + Новый чат
        </button>
        <nav>
          <button className={view === "documents" ? "nav active" : "nav"} onClick={() => setView("documents")}>
            📄 Документы
          </button>
          <button className={view === "settings" ? "nav active" : "nav"} onClick={() => setView("settings")}>
            ⚙️ Настройки
          </button>
        </nav>
        <div className="chat-list">
          {chats.map((c) => (
            <div key={c.id} className={view === "chat" && c.id === activeId ? "chat-item active" : "chat-item"}>
              <button
                className="chat-title"
                onClick={() => {
                  setActiveId(c.id);
                  setView("chat");
                }}
              >
                {c.title}
              </button>
              <button className="icon" title="Удалить чат" onClick={() => removeChat(c.id)}>
                ×
              </button>
            </div>
          ))}
          {chats.length === 0 && <p className="muted small">Чатов пока нет</p>}
        </div>
        <div className="user-box">
          <span className="small muted" title={user.email}>
            {user.email}
          </span>
          <button className="link" onClick={onLogout}>
            Выйти
          </button>
        </div>
      </aside>
      <main className="main">
        {view === "chat" && (
          <ChatView
            key={activeId ?? "none"}
            chatId={activeId}
            onNewChat={newChat}
            onTitleMayChange={reloadChats}
            onGoToDocuments={() => setView("documents")}
          />
        )}
        {view === "documents" && <DocumentsView />}
        {view === "settings" && <SettingsView user={user} onSaved={onUser} />}
      </main>
    </div>
  );
}
