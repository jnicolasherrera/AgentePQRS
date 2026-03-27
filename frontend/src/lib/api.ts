import axios from 'axios';

export const api = axios.create({
  baseURL: `${process.env.NEXT_PUBLIC_API_URL}/api/v2`,
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor: attach token from localStorage
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    try {
      const storeRaw = localStorage.getItem('pqrs-v2-auth');
      if (storeRaw) {
        const store = JSON.parse(storeRaw);
        const token = store?.state?.token;
        if (token) config.headers.Authorization = `Bearer ${token}`;
      }
    } catch {}
  }
  return config;
});

// Response interceptor: on 401, fire session-expired event (do NOT redirect)
// Skip for /auth/ endpoints — those 401s are login failures, not expired sessions
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const isAuthEndpoint = error.config?.url?.includes('/auth/');
    if (
      error.response?.status === 401
      && !error.config._retry
      && !isAuthEndpoint
      && typeof window !== 'undefined'
      && !window.location.pathname.startsWith('/login')
    ) {
      error.config._retry = true;
      window.dispatchEvent(
        new CustomEvent('FLEXPQR_SESSION_EXPIRED', {
          detail: { originalRequest: error.config },
        })
      );
    }
    return Promise.reject(error);
  }
);
