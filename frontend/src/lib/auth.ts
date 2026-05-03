import { create } from "zustand";

export type UserRole = "admin" | "contributor" | "viewer";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
  role: UserRole;
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  setSession: (data: {
    user: AuthUser;
    access_token: string;
    refresh_token: string;
  }) => void;
  setAccessToken: (token: string) => void;
  setUser: (user: AuthUser) => void;
  clear: () => void;
}

const STORAGE_KEY = "meshnest.auth.v1";

function loadFromStorage(): Partial<AuthState> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function persist(state: AuthState) {
  const { user, accessToken, refreshToken } = state;
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ user, accessToken, refreshToken })
  );
}

export const useAuth = create<AuthState>((set, get) => {
  const initial = loadFromStorage();
  return {
    user: (initial.user as AuthUser | undefined) ?? null,
    accessToken: (initial.accessToken as string | undefined) ?? null,
    refreshToken: (initial.refreshToken as string | undefined) ?? null,
    setSession: ({ user, access_token, refresh_token }) => {
      set({ user, accessToken: access_token, refreshToken: refresh_token });
      persist(get());
    },
    setAccessToken: (token) => {
      set({ accessToken: token });
      persist(get());
    },
    setUser: (user) => {
      set({ user });
      persist(get());
    },
    clear: () => {
      set({ user: null, accessToken: null, refreshToken: null });
      localStorage.removeItem(STORAGE_KEY);
    },
  };
});
