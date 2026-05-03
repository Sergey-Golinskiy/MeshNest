import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Boxes } from "lucide-react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { LangSwitcher } from "@/components/LangSwitcher";

export default function LoginPage() {
  const { t } = useTranslation();
  const { setSession, accessToken } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (accessToken) return <Navigate to="/" replace />;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const res = await api.post("/auth/login", { email, password });
      setSession(res.data);
      nav("/", { replace: true });
    } catch {
      setErr(t("auth.invalid_credentials"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-full flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="absolute right-4 top-4">
          <LangSwitcher />
        </div>
        <div className="text-center mb-6">
          <Boxes className="mx-auto h-10 w-10 text-accent" />
          <h1 className="mt-3 text-2xl font-semibold">{t("auth.login_title")}</h1>
          <p className="mt-1 text-sm text-text-muted">{t("app.tagline")}</p>
        </div>
        <form onSubmit={handleSubmit} className="card p-6 space-y-4">
          <label className="block">
            <span className="text-sm text-text-muted">{t("auth.email")}</span>
            <input
              type="email"
              required
              autoFocus
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input mt-1"
            />
          </label>
          <label className="block">
            <span className="text-sm text-text-muted">{t("auth.password")}</span>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input mt-1"
            />
          </label>
          {err && <p className="text-sm text-danger">{err}</p>}
          <button type="submit" disabled={busy} className="btn-primary w-full">
            {t("auth.submit")}
          </button>
        </form>
      </div>
    </div>
  );
}
