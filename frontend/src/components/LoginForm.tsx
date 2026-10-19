import { useState, type FormEvent } from "react";
import { api } from "../api";

export default function LoginForm({ onAuthed }: { onAuthed: (token: string) => Promise<void> }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const { access_token } = await (mode === "login" ? api.login : api.register)(email, password);
      await onAuthed(access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось войти");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center">
      <form className="card auth" onSubmit={submit}>
        <h1>Knowledge Assistant</h1>
        <p className="muted">Вопросы по вашим документам — с источниками</p>
        <label>
          Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
        </label>
        <label>
          Пароль
          <input
            type="password"
            required
            minLength={mode === "register" ? 8 : 1}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {mode === "register" && <span className="small muted">Не короче 8 символов</span>}
        </label>
        {error && <div className="error">{error}</div>}
        <button className="primary" disabled={busy}>
          {busy ? "Подождите…" : mode === "login" ? "Войти" : "Создать аккаунт"}
        </button>
        <button
          type="button"
          className="link"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError("");
          }}
        >
          {mode === "login" ? "Нет аккаунта? Зарегистрироваться" : "Уже есть аккаунт? Войти"}
        </button>
      </form>
    </div>
  );
}
