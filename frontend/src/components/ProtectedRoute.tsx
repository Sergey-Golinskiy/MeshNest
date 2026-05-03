import { Navigate, useLocation } from "react-router-dom";

import { useAuth, type UserRole } from "@/lib/auth";

interface Props {
  children: React.ReactNode;
  roles?: UserRole[];
}

export function ProtectedRoute({ children, roles }: Props) {
  const { user, accessToken } = useAuth();
  const loc = useLocation();
  if (!accessToken || !user) {
    return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  }
  if (roles && !roles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}
