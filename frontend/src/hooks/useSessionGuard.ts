'use client';

import { useEffect, useRef } from 'react';
import { api } from '@/lib/api';

interface PendingRequest {
  config: any;
  resolve: (value: any) => void;
  reject: (reason: any) => void;
}

// Module-level queue (shared across all hook instances)
let pendingQueue: PendingRequest[] = [];
let isReauthing = false;

export function useSessionGuard(onSessionExpired: (config: any) => void) {
  const onSessionExpiredRef = useRef(onSessionExpired);
  onSessionExpiredRef.current = onSessionExpired;

  useEffect(() => {
    const handleExpired = (e: Event) => {
      const event = e as CustomEvent;
      const { originalRequest } = event.detail;

      if (!isReauthing) {
        isReauthing = true;
        onSessionExpiredRef.current(originalRequest);
      }
    };

    const handleSuccess = async (e: Event) => {
      const event = e as CustomEvent;
      const { newToken } = event.detail;

      // Retry all queued requests with the new token
      const queue = [...pendingQueue];
      pendingQueue = [];
      isReauthing = false;

      for (const pending of queue) {
        try {
          pending.config.headers = {
            ...pending.config.headers,
            Authorization: `Bearer ${newToken}`,
          };
          const result = await api.request(pending.config);
          pending.resolve(result);
        } catch (err) {
          pending.reject(err);
        }
      }
    };

    window.addEventListener('FLEXPQR_SESSION_EXPIRED', handleExpired);
    window.addEventListener('FLEXPQR_REAUTH_SUCCESS', handleSuccess);

    return () => {
      window.removeEventListener('FLEXPQR_SESSION_EXPIRED', handleExpired);
      window.removeEventListener('FLEXPQR_REAUTH_SUCCESS', handleSuccess);
    };
  }, []);
}
