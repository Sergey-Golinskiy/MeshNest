import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Copy, Plus, Trash2 } from "lucide-react";

import { api } from "@/lib/api";
import type { InviteOut, UserRole } from "@/types";

export default function AdminInvitesPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const { data } = useQuery({
    queryKey: ["admin-invites"],
    queryFn: () =>
      api.get<InviteOut[]>("/admin/invites").then((r) => r.data),
  });

  const [role, setRole] = useState<UserRole>("viewer");
  const [days, setDays] = useState(7);
  const [hint, setHint] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api.post<InviteOut>("/admin/invites", {
        role,
        expires_in_days: days,
        email_hint: hint || null,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-invites"] }),
  });
  const del = useMutation({
    mutationFn: (id: string) => api.delete(`/admin/invites/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-invites"] }),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{t("admin.invites")}</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
        className="card flex flex-wrap items-end gap-3 p-4"
      >
        <label className="flex flex-col text-xs text-text-muted">
          {t("admin.role")}
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
            className="input mt-1 w-36"
          >
            <option value="viewer">viewer</option>
            <option value="contributor">contributor</option>
            <option value="admin">admin</option>
          </select>
        </label>
        <label className="flex flex-col text-xs text-text-muted">
          {t("admin.expires_in_days")}
          <input
            type="number"
            min={1}
            max={90}
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="input mt-1 w-24"
          />
        </label>
        <label className="flex flex-col text-xs text-text-muted flex-1 min-w-[200px]">
          {t("admin.email_hint")}
          <input
            type="email"
            value={hint}
            onChange={(e) => setHint(e.target.value)}
            className="input mt-1"
          />
        </label>
        <button type="submit" className="btn-primary">
          <Plus className="h-4 w-4" />
          {t("admin.create_invite")}
        </button>
      </form>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-bg-subtle text-left text-text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">Role</th>
              <th className="px-3 py-2 font-medium">Hint</th>
              <th className="px-3 py-2 font-medium">Expires</th>
              <th className="px-3 py-2 font-medium">Used</th>
              <th className="px-3 py-2 font-medium">Link</th>
              <th className="px-3 py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {data?.map((inv) => (
              <tr key={inv.id} className="border-t border-border">
                <td className="px-3 py-2"><span className="chip">{inv.role}</span></td>
                <td className="px-3 py-2 text-text-muted">{inv.email_hint ?? "—"}</td>
                <td className="px-3 py-2 text-text-muted">
                  {new Date(inv.expires_at).toLocaleString()}
                </td>
                <td className="px-3 py-2 text-text-muted">
                  {inv.used_at ? new Date(inv.used_at).toLocaleString() : "—"}
                </td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={() => navigator.clipboard.writeText(inv.invite_url)}
                    title={t("admin.copy_link")}
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                </td>
                <td className="px-3 py-2 text-right">
                  {!inv.used_at && (
                    <button
                      type="button"
                      className="btn-ghost text-danger"
                      onClick={() => del.mutate(inv.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!data?.length && (
              <tr>
                <td colSpan={6} className="px-3 py-12 text-center text-text-muted">
                  No invites.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
