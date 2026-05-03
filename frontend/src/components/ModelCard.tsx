import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Image as ImageIcon, Layers } from "lucide-react";

import type { ModelCard as ModelCardType } from "@/types";
import { cn } from "@/lib/utils";

export function ModelCard({ model }: { model: ModelCardType }) {
  const slides: string[] = [];
  if (model.preview_url) slides.push(model.preview_url);
  for (const t of model.thumbnails) {
    if (!slides.includes(t)) slides.push(t);
  }
  const [idx, setIdx] = useState(0);
  // reset to first slide when model changes
  useEffect(() => setIdx(0), [model.id]);

  return (
    <Link
      to={`/models/${model.slug}`}
      className="card group block overflow-hidden transition hover:shadow-md"
    >
      <div
        className="relative aspect-square w-full overflow-hidden bg-bg-subtle"
        onMouseMove={(e) => {
          if (slides.length <= 1) return;
          const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
          const ratio = (e.clientX - rect.left) / rect.width;
          const next = Math.min(slides.length - 1, Math.max(0, Math.floor(ratio * slides.length)));
          if (next !== idx) setIdx(next);
        }}
        onMouseLeave={() => setIdx(0)}
      >
        {slides.length > 0 ? (
          <>
            {slides.map((src, i) => (
              <img
                key={src + i}
                src={src}
                alt={model.title}
                loading="lazy"
                onError={(e) => {
                  (e.currentTarget as HTMLImageElement).style.display = "none";
                }}
                className={cn(
                  "absolute inset-0 h-full w-full object-cover transition-opacity duration-150",
                  i === idx ? "opacity-100" : "opacity-0",
                )}
              />
            ))}
            {slides.length > 1 && (
              <div className="pointer-events-none absolute bottom-1 left-0 right-0 flex justify-center gap-1">
                {slides.map((_, i) => (
                  <span
                    key={i}
                    className={cn(
                      "h-1 w-3 rounded-full transition-opacity",
                      i === idx ? "bg-white/90 opacity-100" : "bg-white/50 opacity-70",
                    )}
                  />
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-text-subtle">
            <ImageIcon className="h-12 w-12" />
          </div>
        )}
      </div>
      <div className="p-4 space-y-2">
        <div
          className="line-clamp-2 font-medium leading-snug min-h-[2.6em]"
          title={model.title}
        >
          {model.title}
        </div>
        <div className="line-clamp-1 text-xs text-text-muted">
          {model.category_path ?? "uncategorized"}
        </div>
        <div className="flex flex-wrap items-center gap-1">
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
