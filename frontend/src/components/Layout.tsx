import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Boxes, LogOut, ShieldCheck, Upload, ListChecks } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { LangSwitcher } from "@/components/LangSwitcher";
import { cn } from "@/lib/utils";

export function Layout() {
  const { user, clear } = useAuth();
  const nav = useNavigate();
  const { t } = useTranslation();

  if (!user) return null;

  const isAdmin = user.role === "admin";
  const canUpload = user.role === "admin" || user.role === "contributor";

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-30 border-b border-border bg-bg-panel">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
          <Link to="/" className="flex items-center gap-2 text-lg font-semibold">
            <Boxes className="h-5 w-5 text-accent" />
            <span>{t("app.name")}</span>
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            <NavItem to="/" label={t("nav.library")} icon={<Boxes className="h-4 w-4" />} />
            {canUpload && (
              <>
                <NavItem
                  to="/upload"
                  label={t("nav.upload")}
                  icon={<Upload className="h-4 w-4" />}
                />
                <NavItem
                  to="/import-jobs"
                  label={t("nav.import_jobs")}
                  icon={<ListChecks className="h-4 w-4" />}
                />
              </>
            )}
            {isAdmin && (
              <NavItem
                to="/admin/invites"
                label={t("nav.admin")}
                icon={<ShieldCheck className="h-4 w-4" />}
              />
            )}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <LangSwitcher />
            <span className="text-sm text-text-muted hidden sm:inline">
              {user.display_name || user.email}
            </span>
            <button
              type="button"
              onClick={() => {
                clear();
                nav("/login");
              }}
              className="btn-ghost"
              aria-label={t("nav.logout")}
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}

function NavItem({
  to,
  label,
  icon,
}: {
  to: string;
  label: string;
  icon: React.ReactNode;
}) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        cn(
          "flex items-center gap-1.5 rounded px-3 py-1.5 text-text-muted hover:bg-bg-subtle hover:text-text",
          isActive && "bg-bg-subtle text-text"
        )
      }
    >
      {icon}
      {label}
    </NavLink>
  );
}
