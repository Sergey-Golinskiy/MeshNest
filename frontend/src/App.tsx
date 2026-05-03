import { Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Layout } from "@/components/Layout";
import LoginPage from "@/routes/login";
import InviteRedeemPage from "@/routes/invite";
import LibraryPage from "@/routes/library";
import ModelDetailPage from "@/routes/model";
import UploadPage from "@/routes/upload";
import ImportJobsPage from "@/routes/import-jobs";
import AdminInvitesPage from "@/routes/admin/invites";
import AdminUsersPage from "@/routes/admin/users";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/invite/:token" element={<InviteRedeemPage />} />

      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<LibraryPage />} />
        <Route path="/models/:idOrSlug" element={<ModelDetailPage />} />
        <Route
          path="/upload"
          element={
            <ProtectedRoute roles={["admin", "contributor"]}>
              <UploadPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/import-jobs"
          element={
            <ProtectedRoute roles={["admin", "contributor"]}>
              <ImportJobsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/invites"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminInvitesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/users"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminUsersPage />
            </ProtectedRoute>
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
