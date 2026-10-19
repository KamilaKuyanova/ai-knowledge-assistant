import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { api, type DocumentInfo } from "../api";

const STATUS_LABEL: Record<DocumentInfo["status"], string> = {
  processing: "Обрабатывается…",
  ready: "Готов",
  failed: "Ошибка",
};
const ACCEPT = ".pdf,.docx,.txt";

export default function DocumentsView() {
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const reload = useCallback(async () => {
    try {
      setDocs(await api.documents());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить список");
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  // Пока есть документы в обработке — обновляем список раз в 2 секунды.
  const hasProcessing = docs.some((d) => d.status === "processing");
  useEffect(() => {
    if (!hasProcessing) return;
    const t = setInterval(() => void reload(), 2000);
    return () => clearInterval(t);
  }, [hasProcessing, reload]);

  async function upload(files: FileList | File[]) {
    setError("");
    setUploading(true);
    for (const file of Array.from(files)) {
      try {
        await api.upload(file);
      } catch (e) {
        setError(`${file.name}: ${e instanceof Error ? e.message : "не удалось загрузить"}`);
      }
    }
    setUploading(false);
    await reload();
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length) void upload(e.dataTransfer.files);
  }

  async function remove(d: DocumentInfo) {
    if (!confirm(`Удалить «${d.filename}»? Ответы больше не будут на него опираться.`)) return;
    try {
      await api.deleteDocument(d.id);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось удалить");
    }
  }

  return (
    <div className="page">
      <h2>Документы</h2>
      <div
        className={dragging ? "dropzone dragging" : "dropzone"}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => input.current?.click()}
      >
        {uploading ? "Загрузка…" : "Перетащите файлы сюда или нажмите, чтобы выбрать (PDF, DOCX, TXT, до 20 МБ)"}
        <input
          ref={input}
          type="file"
          accept={ACCEPT}
          multiple
          hidden
          onChange={(e) => {
            if (e.target.files?.length) void upload(e.target.files);
            e.target.value = "";
          }}
        />
      </div>
      {error && <div className="error">{error}</div>}
      {loaded && docs.length === 0 && <p className="muted">Документов пока нет.</p>}
      <ul className="doc-list">
        {docs.map((d) => (
          <li key={d.id} className="card doc">
            <div>
              <div className="doc-name">{d.filename}</div>
              <div className="small muted">
                {d.status === "ready" && `${d.chunk_count} фрагм.${d.page_count ? `, ${d.page_count} стр.` : ""} · `}
                {new Date(d.created_at).toLocaleString("ru-RU")}
              </div>
              {d.status === "failed" && d.error && <div className="error small">{d.error}</div>}
            </div>
            <div className="row">
              <span className={`badge ${d.status}`}>{STATUS_LABEL[d.status]}</span>
              <button className="icon" title="Удалить" onClick={() => remove(d)}>
                ×
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
