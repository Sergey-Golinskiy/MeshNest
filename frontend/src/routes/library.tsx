import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Search } from "lucide-react";

import { api } from "@/lib/api";
import { ModelCard } from "@/components/ModelCard";
import { DEFAULT_FILTERS, FilterPanel, type Filters } from "@/components/FilterPanel";
import type { ModelListResponse } from "@/types";

export default function LibraryPage() {
  const { t } = useTranslation();
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["models", filters, q, page],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.category) params.set("category", filters.category);
      if (filters.has_stl) params.set("has_stl", "true");
      if (filters.has_3mf) params.set("has_3mf", "true");
      if (filters.has_step) params.set("has_step", "true");
      if (filters.is_flexi) params.set("is_flexi", "true");
      if (filters.needs_review) params.set("needs_review", "true");
      filters.tags.forEach((t) => params.append("tag", t));
      if (q.trim()) params.set("q", q.trim());
      params.set("page", String(page));
      params.set("page_size", "48");
      const res = await api.get<ModelListResponse>(`/models?${params.toString()}`);
      return res.data;
    },
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[260px_1fr]">
      <FilterPanel
        value={filters}
        onChange={(f) => {
          setFilters(f);
          setPage(1);
        }}
      />
      <section>
        <header className="mb-4 flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">{t("library.title")}</h1>
          <div className="relative ml-auto w-full max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-subtle" />
            <input
              type="search"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
              placeholder={t("library.search_placeholder")}
              className="input pl-9"
            />
          </div>
          {data && (
            <span className="text-sm text-text-muted">
              {data.total.toLocaleString()} models
            </span>
          )}
        </header>

        {isLoading ? (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {Array.from({ length: 12 }).map((_, i) => (
              <div key={i} className="aspect-square rounded-lg bg-bg-subtle animate-pulse" />
            ))}
          </div>
        ) : data && data.items.length === 0 ? (
          <div className="card p-12 text-center text-text-muted">{t("library.empty")}</div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {data?.items.map((m) => (
                <ModelCard key={m.id} model={m} />
              ))}
            </div>
            {data && totalPages > 1 && (
              <div className="mt-6 flex items-center justify-center gap-2">
                <button
                  className="btn-secondary"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Prev
                </button>
                <span className="text-sm text-text-muted">
                  {page} / {totalPages}
                </span>
                <button
                  className="btn-secondary"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
