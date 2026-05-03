import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Boxes } from "lucide-react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { LangSwitcher } from "@/components/LangSwitcher";

interface InviteInfo {
  token: string;
  role: "admin" | "contributor" | "viewer";
  expires_at: string;
  email_hint?: string | null;
  valid: boolean;
}

export default function InviteRedeemPage() {
  const { t } = useTranslation();
  const { token } = useParams<{ token: string }>();
  const { setSession, accessToken } = useAuth();
  const nav = useNavigate();
  const [info, setInfo] = useState<InviteInfo | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) return;
    api
      .get<InviteInfo>(`/auth/invite/${token}/info`)
      .then((r) => {
        setInfo(r.data);
        if (r.data.email_hint) setEmail(r.data.email_hint);
      })
      .catch(() => setInfo({ token: token!, role: "viewer", expires_at: "", valid: false }));
  }, [token]);

  if (accessToken) return <Navigate to="/" replace />;
  if (!token) return <Navigate to="/login" replace />;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const res = await api.post(`/auth/invite/${token}/redeem`, {
        email,
        password,
        display_name: displayName || null,
      });
      setSession(res.data);
      nav("/", { replace: true });
    } catch (e) {
      setErr(t("auth.invalid_invite"));
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
          <h1 className="mt-3 text-2xl font-semibold">{t("auth.invite_title")}</h1>
          {info && info.valid && (
            <p className="mt-1 text-sm text-text-muted">
              role: <span className="font-mono">{info.role}</span>
            </p>
          )}
        </div>
        {info && !info.valid ? (
          <div className="card p-6">
            <p className="text-sm text-danger">{t("auth.invalid_invite")}</p>
          </div>
        ) : (
          <form onSubmit={submit} className="card p-6 space-y-4">
            <label className="block">
              <span className="text-sm text-text-muted">{t("auth.email")}</span>
              <input
                type="email"
                required
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
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input mt-1"
              />
            </label>
            <label className="block">
              <span className="text-sm text-text-muted">{t("auth.display_name")}</span>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="input mt-1"
              />
            </label>
            {err && <p className="text-sm text-danger">{err}</p>}
            <button type="submit" disabled={busy} className="btn-primary w-full">
              {t("auth.register")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
