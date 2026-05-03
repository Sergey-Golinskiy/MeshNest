import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ArrowLeft, CheckCircle2, Download, Image as ImageIcon } from "lucide-react";

import { api } from "@/lib/api";
import { ModelViewer } from "@/components/ModelViewer";
import { useAuth } from "@/lib/auth";
import { formatBytes } from "@/lib/utils";
import type { FileItem, ModelDetail } from "@/types";

export default function ModelDetailPage() {
  const { idOrSlug } = useParams<{ idOrSlug: string }>();
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { user } = useAuth();
  const canMarkReviewed =
    user?.role === "admin" || user?.role === "contributor";

  const [tab, setTab] = useState<"preview" | "viewer" | "files">("preview");

  const { data: model } = useQuery({
    queryKey: ["model", idOrSlug],
    queryFn: () => api.get<ModelDetail>(`/models/${idOrSlug}`).then((r) => r.data),
    enabled: !!idOrSlug,
  });
  const { data: files } = useQuery({
    queryKey: ["model-files", idOrSlug],
    queryFn: () =>
      api.get<FileItem[]>(`/models/${idOrSlug}/files`).then((r) => r.data),
    enabled: !!idOrSlug,
  });

  const markReviewed = useMutation({
    mutationFn: () => api.post(`/models/${idOrSlug}/mark-reviewed`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["model", idOrSlug] }),
  });

  if (!model) {
    return <div className="text-text-muted">Loading…</div>;
  }

  return (
    <article className="space-y-6">
      <header className="flex flex-wrap items-start gap-4">
        <Link to="/" className="btn-ghost">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-semibold">{model.title}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-text-muted">
            <span>{model.category_path ?? "uncategorized"}</span>
            {model.imported_at && (
              <>
                <span>·</span>
                <span>
                  {t("model.imported_at")}: {new Date(model.imported_at).toLocaleDateString()}
                </span>
              </>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-1">
            {model.tags.map((tag) => (
              <span key={tag} className="chip">
                {tag}
              </span>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={`/api/v1/models/${model.slug}/download`}
            className="btn-primary"
            target="_blank"
            rel="noreferrer"
          >
            <Download className="h-4 w-4" />
            {t("model.download_zip")}
          </a>
          {canMarkReviewed && !model.is_reviewed && (
            <button
              type="button"
              className="btn-secondary"
              onClick={() => markReviewed.mutate()}
              disabled={markReviewed.isPending}
            >
              <CheckCircle2 className="h-4 w-4" />
              {t("model.mark_reviewed")}
            </button>
          )}
        </div>
      </header>

      <div className="border-b border-border">
        <nav className="flex gap-1 text-sm">
          {(
            [
              ["preview", t("model.preview")],
              ["viewer", t("model.viewer")],
              ["files", `${t("model.files")} · ${files?.length ?? 0}`],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              onClick={() => setTab(k)}
              className={`-mb-px border-b-2 px-3 py-2 ${
                tab === k
                  ? "border-accent text-text"
                  : "border-transparent text-text-muted hover:text-text"
              }`}
            >
              {label}
            </button>
          ))}
        </nav>
      </div>

      {tab === "preview" && (
        <div className="card overflow-hidden">
          {model.preview_url ? (
            <img
              src={model.preview_url}
              alt={model.title}
              className="max-h-[600px] w-full object-contain bg-bg-subtle"
            />
          ) : (
            <div className="flex h-[400px] items-center justify-center text-text-subtle">
              <ImageIcon className="h-16 w-16" />
            </div>
          )}
        </div>
      )}

      {tab === "viewer" && (
        <ModelViewer modelIdOrSlug={model.slug} status={model.viewer_status} />
      )}

      {tab === "files" && files && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-bg-subtle text-left text-text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">File</th>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="px-3 py-2 font-medium">Role</th>
                <th className="px-3 py-2 text-right font-medium">Size</th>
                <th className="px-3 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {files.map((f) => (
                <tr key={f.id} className="border-t border-border">
                  <td className="px-3 py-2 font-mono text-xs">{f.file_name}</td>
                  <td className="px-3 py-2">{f.file_type}</td>
                  <td className="px-3 py-2 text-text-muted">{f.role}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatBytes(f.size_bytes)}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <a
                      href={f.download_url}
                      className="text-accent hover:underline"
                      target="_blank"
                      rel="noreferrer"
                    >
                      <Download className="inline h-4 w-4" />
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <section className="card p-4 text-sm">
        <h2 className="mb-2 font-semibold">{t("model.metadata")}</h2>
        <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <Field label={t("model.source")} value={model.source_name ?? "—"} />
          <Field label="SHA256" value={model.source_hash ?? "—"} mono />
          <Field
            label="Counts"
            value={`STL ${model.stl_count} · 3MF ${model.three_mf_count} · STEP ${model.step_count} · IMG ${model.image_count} · VID ${model.video_count}`}
          />
          <Field label="Status" value={`${model.status} · viewer:${model.viewer_status}`} />
        </dl>
      </section>
    </article>
  );
}

function Field({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-text-muted">{label}</dt>
      <dd className={mono ? "font-mono text-xs break-all" : ""}>{value}</dd>
    </div>
  );
}
