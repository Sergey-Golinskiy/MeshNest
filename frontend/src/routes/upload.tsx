import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Upload as UploadIcon, Loader2 } from "lucide-react";

import { api, rawPutChunk } from "@/lib/api";
import { formatBytes, sha256Hex } from "@/lib/utils";

interface InitResponse {
  upload_id: string;
  chunk_size: number;
  total_chunks: number;
}

export default function UploadPage() {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<"idle" | "hashing" | "uploading" | "finalizing" | "done" | "error">("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function start() {
    if (!file) return;
    setErr(null);
    setProgress(0);
    setJobId(null);

    try {
      // 1. SHA256 (опц.) — очень большие файлы могут тормозить, делаем по chunks
      // Для MVP: пропускаем глобальный sha256 (передаём null), сервер сам посчитает.

      // 2. init
      setStatus("uploading");
      const init = await api.post<InitResponse>("/uploads/init", {
        filename: file.name,
        total_size: file.size,
      });
      const { upload_id, chunk_size, total_chunks } = init.data;

      // 3. parallel chunks (3 одновременно)
      const concurrency = 3;
      let nextChunk = 0;
      let done = 0;

      async function worker() {
        while (true) {
          const myIndex = nextChunk++;
          if (myIndex >= total_chunks) return;
          const start = myIndex * chunk_size;
          const end = Math.min(file!.size, start + chunk_size);
          const blob = file!.slice(start, end);
          await rawPutChunk(upload_id, myIndex, blob);
          done++;
          setProgress(Math.floor((done / total_chunks) * 100));
        }
      }
      await Promise.all(Array.from({ length: concurrency }, worker));

      // 4. complete
      setStatus("finalizing");
      await api.post(`/uploads/${upload_id}/complete`);

      // 5. trigger import
      const r = await api.post<{ import_job_id: string }>("/import-package", {
        upload_id,
      });
      setJobId(r.data.import_job_id);
      setStatus("done");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setErr(msg);
      setStatus("error");
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold mb-6">{t("upload.title")}</h1>

      <div className="card p-6 space-y-4">
        <label className="flex flex-col items-center gap-3 rounded-lg border-2 border-dashed border-border p-8 cursor-pointer hover:bg-bg-subtle">
          <UploadIcon className="h-8 w-8 text-text-muted" />
          <span className="text-sm text-text-muted">{t("upload.select_file")}</span>
          <input
            type="file"
            accept=".zip"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setStatus("idle");
              setProgress(0);
              setJobId(null);
              setErr(null);
            }}
            className="hidden"
          />
          {file && (
            <span className="text-sm font-mono">
              {file.name} · {formatBytes(file.size)}
            </span>
          )}
        </label>

        {(status === "uploading" || status === "finalizing") && (
          <div>
            <div className="h-2 w-full overflow-hidden rounded bg-bg-subtle">
              <div
                className="h-full bg-accent transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="mt-2 flex items-center gap-2 text-sm text-text-muted">
              <Loader2 className="h-4 w-4 animate-spin" />
              {status === "finalizing"
                ? t("upload.finalizing")
                : t("upload.uploading", { percent: progress })}
            </p>
          </div>
        )}

        {status === "done" && jobId && (
          <p className="text-sm text-success">
            {t("upload.success", { job: jobId })}
          </p>
        )}

        {err && <p className="text-sm text-danger">{t("upload.error", { error: err })}</p>}

        <button
          type="button"
          className="btn-primary"
          disabled={!file || status === "uploading" || status === "finalizing"}
          onClick={start}
        >
          Start upload
        </button>
      </div>
    </div>
  );
}
