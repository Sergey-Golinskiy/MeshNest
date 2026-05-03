import { Link } from "react-router-dom";
import { Image as ImageIcon, Layers } from "lucide-react";

import type { ModelCard as ModelCardType } from "@/types";
import { cn } from "@/lib/utils";

export function ModelCard({ model }: { model: ModelCardType }) {
  return (
    <Link
      to={`/models/${model.slug}`}
      className="card group block overflow-hidden transition hover:shadow-md"
    >
      <div className="aspect-square w-full overflow-hidden bg-bg-subtle">
        {model.preview_url ? (
          <img
            src={model.preview_url}
            alt={model.title}
            loading="lazy"
            className="h-full w-full object-cover transition group-hover:scale-[1.02]"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-text-subtle">
            <ImageIcon className="h-12 w-12" />
          </div>
        )}
      </div>
      <div className="p-3">
        <div className="line-clamp-1 font-medium" title={model.title}>
          {model.title}
        </div>
        <div className="mt-0.5 line-clamp-1 text-xs text-text-muted">
          {model.category_path ?? "uncategorized"}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-1">
          <FormatBadge label="STL" present={model.has_stl} />
          <FormatBadge label="STEP" present={model.has_step} />
          <FormatBadge label="3MF" present={model.has_3mf} />
          {model.has_video && <FormatBadge label="VIDEO" present />}
          <span className="ml-auto inline-flex items-center gap-1 text-xs text-text-muted">
            <Layers className="h-3 w-3" />
            {model.file_count}
          </span>
        </div>
      </div>
    </Link>
  );
}

function FormatBadge({ label, present }: { label: string; present: boolean }) {
  return (
    <span
      className={cn(
        "rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        present
          ? "bg-accent-subtle text-accent"
          : "bg-bg-subtle text-text-subtle line-through"
      )}
    >
      {label}
    </span>
  );
}
