'use client';

import React, { useState } from 'react';
import axios from 'axios';
import { useAuthStore } from '@/store/authStore';

interface ReAuthModalProps {
  originalRequest: any;
  onSuccess: () => void;
}

export function ReAuthModal({ originalRequest, onSuccess }: ReAuthModalProps) {
  const { user, setAuth, clearAuth } = useAuthStore();
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [attemptsLeft, setAttemptsLeft] = useState(3);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user?.email) return;
    setLoading(true);
    setError('');

    try {
      const res = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v2/auth/login`,
        { email: user.email, password }
      );
      const { access_token, user: updatedUser } = res.data;
      setAuth(access_token, updatedUser);

      window.dispatchEvent(
        new CustomEvent('FLEXPQR_REAUTH_SUCCESS', {
          detail: { originalRequest, newToken: access_token },
        })
      );
      onSuccess();
    } catch {
      const remaining = attemptsLeft - 1;
      setAttemptsLeft(remaining);
      if (remaining <= 0) {
        clearAuth();
        window.location.href = '/login';
        return;
      } else {
        setError(`Contraseña incorrecta. ${remaining} ${remaining === 1 ? 'intento restante' : 'intentos restantes'}.`);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    clearAuth();
    window.location.href = '/login';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        className="w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl"
        style={{ border: '2px solid #035aa7' }}
      >
        {/* Header */}
        <div className="mb-6 text-center">
          <div
            className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full"
            style={{ backgroundColor: '#021f59' }}
          >
            <svg className="h-7 w-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold" style={{ color: '#021f59' }}>
            Tu sesión ha expirado
          </h2>
          <p className="mt-2 text-sm text-gray-500">
            Por seguridad, confirma tu contraseña para continuar donde lo dejaste.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Email read-only */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Email</label>
            <input
              type="email"
              value={user?.email ?? ''}
              readOnly
              className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm text-gray-500"
            />
          </div>

          {/* Password with toggle */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Contraseña</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Ingresa tu contraseña"
                required
                autoFocus
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 pr-11 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
                style={{ borderColor: error ? '#ef4444' : undefined }}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showPassword ? (
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 4.411m0 0L21 21" />
                  </svg>
                ) : (
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          {/* Error message */}
          {error && (
            <p className="text-sm font-medium text-red-600">{error}</p>
          )}

          {/* Attempts counter */}
          {attemptsLeft < 3 && (
            <p className="text-xs text-amber-600">
              ⚠️ {attemptsLeft} {attemptsLeft === 1 ? 'intento restante' : 'intentos restantes'}
            </p>
          )}

          {/* Buttons */}
          <div className="flex flex-col gap-3 pt-2">
            <button
              type="submit"
              disabled={loading || !password}
              className="w-full rounded-lg py-2.5 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
              style={{ backgroundColor: '#035aa7' }}
            >
              {loading ? 'Verificando...' : 'Continuar trabajando'}
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="w-full rounded-lg border border-gray-200 py-2.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50"
            >
              Cerrar sesión
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
