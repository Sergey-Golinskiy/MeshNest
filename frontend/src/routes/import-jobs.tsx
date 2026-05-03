import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/lib/api";
import type { ImportJob } from "@/types";

export default function ImportJobsPage() {
  const { t } = useTranslation();
  const { data } = useQuery({
    queryKey: ["import-jobs"],
    queryFn: () => api.get<ImportJob[]>("/import-jobs").then((r) => r.data),
    refetchInterval: 5000,
  });

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold">{t("import_jobs.title")}</h1>
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-bg-subtle text-left text-text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">ID</th>
              <th className="px-3 py-2 font-medium">{t("import_jobs.status")}</th>
              <th className="px-3 py-2 font-medium">{t("import_jobs.progress")}</th>
              <th className="px-3 py-2 text-right font-medium">{t("import_jobs.models")}</th>
              <th className="px-3 py-2 text-right font-medium">{t("import_jobs.files")}</th>
              <th className="px-3 py-2 text-right font-medium">{t("import_jobs.warnings")}</th>
              <th className="px-3 py-2 font-medium">{t("import_jobs.started")}</th>
              <th className="px-3 py-2 font-medium">{t("import_jobs.finished")}</th>
            </tr>
          </thead>
          <tbody>
            {data?.map((j) => (
              <tr key={j.id} className="border-t border-border">
                <td className="px-3 py-2 font-mono text-xs">{j.id.slice(0, 8)}…</td>
                <td className="px-3 py-2">
                  <StatusBadge status={j.status} />
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-24 overflow-hidden rounded bg-bg-subtle">
                      <div
                        className="h-full bg-accent"
                        style={{ width: `${j.progress_pct}%` }}
                      />
                    </div>
                    <span className="text-xs tabular-nums text-text-muted">
                      {j.progress_pct}%
                    </span>
                  </div>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{j.models_created}</td>
                <td className="px-3 py-2 text-right tabular-nums">{j.files_processed}</td>
                <td className="px-3 py-2 text-right tabular-nums">{j.warnings_count}</td>
                <td className="px-3 py-2 text-text-muted">
                  {j.started_at ? new Date(j.started_at).toLocaleString() : "—"}
                </td>
                <td className="px-3 py-2 text-text-muted">
                  {j.finished_at ? new Date(j.finished_at).toLocaleString() : "—"}
                </td>
              </tr>
            ))}
            {!data?.length && (
              <tr>
                <td colSpan={8} className="px-3 py-12 text-center text-text-muted">
                  No import jobs yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    queued: "bg-bg-subtle text-text-muted",
    extracting: "bg-accent-subtle text-accent",
    scanning: "bg-accent-subtle text-accent",
    completed: "bg-success-subtle text-success",
    completed_with_warnings: "bg-warn-subtle text-warn",
    failed: "bg-danger-subtle text-danger",
  };
  return (
    <span className={`chip ${colors[status] ?? "bg-bg-subtle"}`}>{status}</span>
  );
}
