import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { useAuth } from "./auth";

export const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

// Request: attach access token
api.interceptors.request.use((config) => {
  const token = useAuth.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response: refresh on 401 (single-flight)
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = useAuth.getState().refreshToken;
  if (!refreshToken) return null;
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const res = await axios.post(
        "/api/v1/auth/refresh",
        { refresh_token: refreshToken },
        { headers: { "Content-Type": "application/json" } }
      );
      const newAccess = res.data.access_token as string;
      useAuth.getState().setAccessToken(newAccess);
      return newAccess;
    } catch {
      useAuth.getState().clear();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

api.interceptors.response.use(
  (r) => r,
  async (err: AxiosError) => {
    const original = err.config as
      | (InternalAxiosRequestConfig & { _retried?: boolean })
      | undefined;
    if (err.response?.status === 401 && original && !original._retried) {
      original._retried = true;
      const newToken = await refreshAccessToken();
      if (newToken) {
        original.headers = original.headers ?? {};
        (original.headers as Record<string, string>).Authorization = `Bearer ${newToken}`;
        return api.request(original);
      }
    }
    return Promise.reject(err);
  }
);

export async function rawPutChunk(
  uploadId: string,
  chunkIndex: number,
  data: Blob
): Promise<void> {
  const token = useAuth.getState().accessToken;
  await axios.put(`/api/v1/uploads/${uploadId}/chunk?n=${chunkIndex}`, data, {
    headers: {
      "Content-Type": "application/octet-stream",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    maxBodyLength: Infinity,
    maxContentLength: Infinity,
  });
}
