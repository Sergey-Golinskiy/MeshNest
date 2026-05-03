import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { User, UserRole } from "@/types";

export default function AdminUsersPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { user: me } = useAuth();

  const { data } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => api.get<User[]>("/admin/users").then((r) => r.data),
  });

  const patch = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { role?: UserRole; is_active?: boolean } }) =>
      api.patch(`/admin/users/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold">{t("admin.users")}</h1>
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-bg-subtle text-left text-text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">Email</th>
              <th className="px-3 py-2 font-medium">Display name</th>
              <th className="px-3 py-2 font-medium">{t("admin.role")}</th>
              <th className="px-3 py-2 font-medium">Active</th>
              <th className="px-3 py-2 font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {data?.map((u) => (
              <tr key={u.id} className="border-t border-border">
                <td className="px-3 py-2 font-mono text-xs">{u.email}</td>
                <td className="px-3 py-2">{u.display_name ?? "—"}</td>
                <td className="px-3 py-2">
                  <select
                    value={u.role}
                    disabled={u.id === me?.id}
                    onChange={(e) =>
                      patch.mutate({
                        id: u.id,
                        body: { role: e.target.value as UserRole },
                      })
                    }
                    className="input w-32"
                  >
                    <option value="viewer">viewer</option>
                    <option value="contributor">contributor</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
                <td className="px-3 py-2">
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={u.is_active}
                      disabled={u.id === me?.id}
                      onChange={(e) =>
                        patch.mutate({
                          id: u.id,
                          body: { is_active: e.target.checked },
                        })
                      }
                    />
                    {u.is_active ? "yes" : "no"}
                  </label>
                </td>
                <td className="px-3 py-2 text-text-muted">
                  {new Date(u.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
