import { useState, type FormEvent } from "react";
import { api, type User } from "../api";

export default function SettingsView({ user, onSaved }: { user: User; onSaved: (u: User) => void }) {
  const [topK, setTopK] = useState(user.settings.top_k);
  const [minScore, setMinScore] = useState(user.settings.min_score);
  const [status, setStatus] = useState<"" | "saved" | string>("");

  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      onSaved(await api.saveSettings({ top_k: topK, min_score: minScore }));
      setStatus("saved");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Не удалось сохранить");
    }
  }

  return (
    <div className="page">
      <h2>Настройки поиска</h2>
      <form className="card settings" onSubmit={save}>
        <label>
          Сколько фрагментов передавать модели: <b>{topK}</b>
          <input type="range" min={1} max={15} value={topK} onChange={(e) => setTopK(+e.target.value)} />
          <span className="small muted">Больше фрагментов — шире контекст, но дольше и точнее может быть путаница.</span>
        </label>
        <label>
          Порог релевантности: <b>{minScore.toFixed(2)}</b>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={minScore}
            onChange={(e) => setMinScore(+e.target.value)}
          />
          <span className="small muted">
            Выше — система чаще отвечает «не нашёл», ниже — чаще пытается ответить по слабо подходящим фрагментам.
          </span>
        </label>
        <div className="row">
          <button className="primary">Сохранить</button>
          {status === "saved" && <span className="muted">Сохранено</span>}
          {status && status !== "saved" && <span className="error">{status}</span>}
        </div>
      </form>
    </div>
  );
}
