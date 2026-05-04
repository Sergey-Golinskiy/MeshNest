import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Upload as UploadIcon, Loader2, X } from "lucide-react";

import { api } from "@/lib/api";
import { formatBytes, cn } from "@/lib/utils";
import type { ModelDetail } from "@/types";

export default function UploadPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [tags, setTags] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<"idle" | "uploading" | "error">("idle");
  const [progress, setProgress] = useState(0);
  const [err, setErr] = useState<string | null>(null);

  function addFiles(newFiles: FileList | File[]) {
    setFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name + ":" + f.size));
      const added: File[] = [];
      for (const f of Array.from(newFiles)) {
        if (!existing.has(f.name + ":" + f.size)) added.push(f);
      }
      return [...prev, ...added];
    });
  }

  function removeFile(idx: number) {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  }

  async function submit() {
    if (files.length === 0) {
      setErr(t("upload.no_files"));
      return;
    }
    if (!title.trim() && files.length === 1) {
      // derive default title from filename without extension
      setTitle(files[0].name.replace(/\.[^.]+$/, ""));
    }
    const finalTitle = title.trim() || files[0].name.replace(/\.[^.]+$/, "");

    setErr(null);
    setProgress(0);
    setStatus("uploading");

    const fd = new FormData();
    fd.append("title", finalTitle);
    if (category.trim()) fd.append("category", category.trim());
    if (tags.trim()) fd.append("tags", tags.trim());
    for (const f of files) fd.append("files", f, f.name);

    try {
      const r = await api.post<ModelDetail>("/models", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => {
          if (e.total) setProgress(Math.round((e.loaded / e.total) * 100));
        },
      });
      navigate(`/models/${r.data.slug}`);
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } }; message?: string })
          ?.response?.data?.detail ??
        (e as Error)?.message ??
        String(e);
      setErr(msg);
      setStatus("error");
    }
  }

  const totalSize = files.reduce((s, f) => s + f.size, 0);

  return (
    <div className="max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">{t("upload.title")}</h1>
        <p className="mt-1 text-sm text-text-muted">{t("upload.hint")}</p>
      </header>

      <div className="card space-y-4 p-6">
        <div>
          <label className="block text-sm font-medium" htmlFor="title">
            {t("upload.model_title")}
          </label>
          <input
            id="title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t("upload.title_placeholder")}
            className="input mt-1"
          />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-sm font-medium" htmlFor="category">
              {t("upload.category")}
            </label>
            <input
              id="category"
              type="text"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="animals/cats"
              className="input mt-1 font-mono text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium" htmlFor="tags">
              {t("upload.tags")}
            </label>
            <input
              id="tags"
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="flexi, articulated"
              className="input mt-1 font-mono text-sm"
            />
          </div>
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = "copy";
          }}
          onDrop={(e) => {
            e.preventDefault();
            if (e.dataTransfer.files) addFiles(e.dataTransfer.files);
          }}
          onClick={() => inputRef.current?.click()}
          className="flex cursor-pointer flex-col items-center gap-3 rounded-lg border-2 border-dashed border-border p-10 text-center hover:bg-bg-subtle"
        >
          <UploadIcon className="h-10 w-10 text-text-muted" />
          <div className="font-medium">{t("upload.drop_here")}</div>
          <div className="text-sm text-text-muted">{t("upload.formats")}</div>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".stl,.step,.stp,.3mf,.obj,.fbx,.zip,.jpg,.jpeg,.png,.webp,.bmp,.mp4,.mov,.webm,.txt,.md,.pdf"
            onChange={(e) => {
              if (e.target.files) addFiles(e.target.files);
              e.target.value = "";
            }}
            className="hidden"
          />
        </div>

        {files.length > 0 && (
          <div className="rounded border border-border">
            <div className="flex items-center justify-between border-b border-border bg-bg-subtle px-3 py-2 text-sm">
              <span>
                {files.length} {t("upload.files_count")} · {formatBytes(totalSize)}
              </span>
              <button
                type="button"
                onClick={() => setFiles([])}
                className="text-xs text-text-muted hover:text-text"
              >
                {t("upload.clear")}
              </button>
            </div>
            <ul className="divide-y divide-border">
              {files.map((f, i) => (
                <li key={i} className="flex items-center gap-3 px-3 py-2 text-sm">
                  <span className="flex-1 truncate font-mono text-xs">{f.name}</span>
                  <span className="text-xs text-text-muted tabular-nums">
                    {formatBytes(f.size)}
                  </span>
                  <button
                    type="button"
                    onClick={() => removeFile(i)}
                    className="text-text-muted hover:text-danger"
                    disabled={status === "uploading"}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {status === "uploading" && (
          <div>
            <div className="h-2 w-full overflow-hidden rounded bg-bg-subtle">
              <div
                className="h-full bg-accent transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="mt-2 flex items-center gap-2 text-sm text-text-muted">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t("upload.uploading", { percent: progress })}
            </p>
          </div>
        )}

        {err && (
          <p className="text-sm text-danger">{t("upload.error", { error: err })}</p>
        )}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            className={cn(
              "btn-primary",
              (files.length === 0 || status === "uploading") && "cursor-not-allowed opacity-50",
            )}
            disabled={files.length === 0 || status === "uploading"}
            onClick={submit}
          >
            <UploadIcon className="h-4 w-4" />
            {t("upload.submit")}
          </button>
        </div>
      </div>
    </div>
  );
}
