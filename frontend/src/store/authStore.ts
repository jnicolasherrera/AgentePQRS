import { create } from "zustand";
import { persist } from "zustand/middleware";
export { api } from "@/lib/api";
import { api } from "@/lib/api";

interface AuthUser {
  id: string;
  email: string;
  nombre: string;
  rol: string;
  tenant_uuid: string;
  cliente_nombre: string;
  debe_cambiar_password: boolean;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  setAuth: (token: string, user: AuthUser) => void;
  clearAuth: () => void;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      setAuth: (token, user) => set({ token, user, isAuthenticated: true }),
      clearAuth: () => set({ token: null, user: null, isAuthenticated: false }),
      login: async (email: string, password: string) => {
        try {
          const response = await api.post("/auth/login", { email, password });
          if (response.data && response.data.access_token) {
            set({
              token: response.data.access_token,
              isAuthenticated: true,
              user: response.data.user,
            });
            return true;
          }
          return false;
        } catch (error) {
          console.error("Login Error:", error);
          return false;
        }
      },
      logout: () => {
        set({ token: null, user: null, isAuthenticated: false });
        window.location.href = "/login";
      },
    }),
    {
      name: "pqrs-v2-auth",
    }
  )
);
