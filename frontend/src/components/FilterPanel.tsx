import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/lib/api";
import type { CategoryNode, TagOut } from "@/types";
import { cn } from "@/lib/utils";

export interface Filters {
  category: string | null;
  tags: string[];
  has_stl: boolean | null;
  has_3mf: boolean | null;
  has_step: boolean | null;
  is_flexi: boolean | null;
  needs_review: boolean | null;
}

export const DEFAULT_FILTERS: Filters = {
  category: null,
  tags: [],
  has_stl: null,
  has_3mf: null,
  has_step: null,
  is_flexi: null,
  needs_review: null,
};

export function FilterPanel({
  value,
  onChange,
}: {
  value: Filters;
  onChange: (next: Filters) => void;
}) {
  const { t } = useTranslation();
  const { data: cats } = useQuery({
    queryKey: ["categories"],
    queryFn: () => api.get<CategoryNode[]>("/categories").then((r) => r.data),
  });
  const { data: tags } = useQuery({
    queryKey: ["tags"],
    queryFn: () => api.get<TagOut[]>("/tags").then((r) => r.data),
  });

  return (
    <aside className="space-y-6 text-sm">
      <section>
        <h3 className="mb-2 font-semibold">{t("library.filter_categories")}</h3>
        <ul className="space-y-1">
          <CatItem
            label="All"
            count={cats?.reduce((a, c) => a + c.model_count + sumChildren(c), 0) ?? 0}
            active={value.category === null}
            onClick={() => onChange({ ...value, category: null })}
          />
          {cats?.map((c) => (
            <CatTree
              key={c.id}
              node={c}
              activePath={value.category}
              onSelect={(path) => onChange({ ...value, category: path })}
            />
          ))}
        </ul>
      </section>

      <section>
        <h3 className="mb-2 font-semibold">{t("library.filter_format")}</h3>
        <div className="flex flex-wrap gap-1">
          {(
            [
              ["has_stl", "STL"],
              ["has_3mf", "3MF"],
              ["has_step", "STEP"],
              ["is_flexi", "Flexi"],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              onClick={() =>
                onChange({ ...value, [k]: value[k] ? null : true })
              }
              className={cn(
                "chip cursor-pointer",
                value[k] && "bg-accent-subtle text-accent"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      <section>
        <h3 className="mb-2 font-semibold">{t("library.filter_status")}</h3>
        <button
          type="button"
          onClick={() =>
            onChange({ ...value, needs_review: value.needs_review ? null : true })
          }
          className={cn(
            "chip cursor-pointer",
            value.needs_review && "bg-warn-subtle text-warn"
          )}
        >
          {t("library.needs_review")}
        </button>
      </section>

      <section>
        <h3 className="mb-2 font-semibold">{t("library.filter_tags")}</h3>
        <div className="flex max-h-72 flex-wrap gap-1 overflow-auto">
          {tags?.slice(0, 100).map((tg) => {
            const active = value.tags.includes(tg.slug);
            return (
              <button
                key={tg.id}
                type="button"
                onClick={() =>
                  onChange({
                    ...value,
                    tags: active
                      ? value.tags.filter((s) => s !== tg.slug)
                      : [...value.tags, tg.slug],
                  })
                }
                className={cn(
                  "chip cursor-pointer",
                  active && "bg-accent-subtle text-accent"
                )}
              >
                {tg.slug}
                <span className="text-text-subtle">·{tg.model_count}</span>
              </button>
            );
          })}
        </div>
      </section>
    </aside>
  );
}

function sumChildren(c: CategoryNode): number {
  return c.children.reduce((a, ch) => a + ch.model_count + sumChildren(ch), 0);
}

function CatTree({
  node,
  activePath,
  onSelect,
  depth = 0,
}: {
  node: CategoryNode;
  activePath: string | null;
  onSelect: (path: string) => void;
  depth?: number;
}) {
  const total = node.model_count + sumChildren(node);
  return (
    <>
      <CatItem
        label={node.name}
        count={total}
        active={activePath === node.path}
        onClick={() => onSelect(node.path)}
        depth={depth}
      />
      {node.children.map((c) => (
        <CatTree
          key={c.id}
          node={c}
          activePath={activePath}
          onSelect={onSelect}
          depth={depth + 1}
        />
      ))}
    </>
  );
}

function CatItem({
  label,
  count,
  active,
  onClick,
  depth = 0,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
  depth?: number;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        className={cn(
          "flex w-full items-center justify-between rounded px-2 py-1 text-left hover:bg-bg-subtle",
          active && "bg-accent-subtle text-accent"
        )}
      >
        <span className="line-clamp-1">{label}</span>
        <span className="text-xs text-text-subtle">{count}</span>
      </button>
    </li>
  );
}
