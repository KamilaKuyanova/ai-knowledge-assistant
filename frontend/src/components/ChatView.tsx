import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { api, type Message, type Source } from "../api";

interface Props {
  chatId: number | null;
  onNewChat: () => void;
  onTitleMayChange: () => void;
  onGoToDocuments: () => void;
}

export default function ChatView({ chatId, onNewChat, onTitleMayChange, onGoToDocuments }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatId === null) return;
    api.messages(chatId).then(setMessages).catch((e) => setError(e.message));
  }, [chatId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  if (chatId === null) {
    return (
      <div className="center empty">
        <h2>Спросите что-нибудь по вашим документам</h2>
        <p className="muted">Сначала загрузите файлы, затем создайте чат и задайте вопрос.</p>
        <div className="row">
          <button className="primary" onClick={onNewChat}>
            + Новый чат
          </button>
          <button onClick={onGoToDocuments}>Загрузить документы</button>
        </div>
      </div>
    );
  }

  async function send(e?: FormEvent) {
    e?.preventDefault();
    const text = question.trim();
    if (!text || pending !== null || chatId === null) return;
    setQuestion("");
    setError("");
    setPending(text);
    try {
      const reply = await api.ask(chatId, text);
      const now = new Date().toISOString();
      setMessages((m) => [...m, { id: -Date.now(), role: "user", content: text, sources: [], answered: true, created_at: now }, reply]);
      onTitleMayChange();
    } catch (err) {
      setQuestion(text); // не теряем вопрос, если запрос не прошёл
      setError(err instanceof Error ? err.message : "Не удалось получить ответ");
    } finally {
      setPending(null);
    }
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  return (
    <div className="chat">
      <div className="messages">
        {messages.length === 0 && pending === null && (
          <p className="muted center-text">Задайте первый вопрос, например: «Как оформить отпуск?»</p>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {pending !== null && (
          <>
            <div className="bubble user">{pending}</div>
            <div className="bubble assistant muted">Ищу в документах…</div>
          </>
        )}
        <div ref={bottomRef} />
      </div>
      {error && <div className="error">{error}</div>}
      <form className="composer" onSubmit={send}>
        <textarea
          rows={2}
          value={question}
          placeholder="Ваш вопрос (Enter — отправить, Shift+Enter — новая строка)"
          maxLength={2000}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={onKey}
        />
        <button className="primary" disabled={pending !== null || !question.trim()}>
          Отправить
        </button>
      </form>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  if (message.role === "user") return <div className="bubble user">{message.content}</div>;
  return (
    <div className={message.answered ? "bubble assistant" : "bubble assistant refusal"}>
      <div className="answer">{message.content}</div>
      {message.sources.length > 0 && (
        <div className="sources">
          <div className="small muted">Источники</div>
          {message.sources.map((s, i) => (
            <SourceCard key={i} index={i + 1} source={s} />
          ))}
        </div>
      )}
    </div>
  );
}

function SourceCard({ index, source }: { index: number; source: Source }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="source">
      <button className="source-head" onClick={() => setOpen(!open)}>
        <span>
          {index}. {source.filename}
          {source.page ? `, стр. ${source.page}` : ""}
        </span>
        <span className="small muted">релевантность {Math.round(source.score * 100)}% {open ? "▲" : "▼"}</span>
      </button>
      {open && <blockquote>{source.quote}</blockquote>}
    </div>
  );
}
