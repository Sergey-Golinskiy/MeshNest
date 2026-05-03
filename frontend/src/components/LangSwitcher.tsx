import { Globe } from "lucide-react";
import { useTranslation } from "react-i18next";

import { cn } from "@/lib/utils";

export function LangSwitcher() {
  const { i18n } = useTranslation();
  const cur = (i18n.resolvedLanguage ?? i18n.language ?? "en").split("-")[0];

  return (
    <div className="flex items-center gap-1 rounded border border-border p-0.5 text-xs">
      <Globe className="ml-1 h-3.5 w-3.5 text-text-muted" />
      {(["en", "uk"] as const).map((lng) => (
        <button
          key={lng}
          type="button"
          onClick={() => i18n.changeLanguage(lng)}
          className={cn(
            "rounded px-2 py-0.5 uppercase transition",
            cur === lng ? "bg-accent text-white" : "text-text-muted hover:bg-bg-subtle"
          )}
        >
          {lng}
        </button>
      ))}
    </div>
  );
}
