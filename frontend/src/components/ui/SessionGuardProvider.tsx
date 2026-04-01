'use client';

import React, { useState, useCallback } from 'react';
import { ReAuthModal } from './ReAuthModal';
import { ForceChangePasswordModal } from './ForceChangePasswordModal';
import { useSessionGuard } from '@/hooks/useSessionGuard';
import { useAuthStore } from '@/store/authStore';

interface SessionGuardProviderProps {
  children: React.ReactNode;
}

export function SessionGuardProvider({ children }: SessionGuardProviderProps) {
  const [sessionExpired, setSessionExpired] = useState(false);
  const [pendingRequest, setPendingRequest] = useState<any>(null);
  const { user, isAuthenticated } = useAuthStore();

  const mustChangePassword = isAuthenticated && user?.debe_cambiar_password === true;

  const handleSessionExpired = useCallback((originalRequest: any) => {
    setPendingRequest(originalRequest);
    setSessionExpired(true);
  }, []);

  useSessionGuard(handleSessionExpired);

  const handleReAuthSuccess = useCallback(() => {
    setSessionExpired(false);
    setPendingRequest(null);
  }, []);

  return (
    <>
      {children}
      {mustChangePassword && <ForceChangePasswordModal />}
      {sessionExpired && pendingRequest && (
        <ReAuthModal
          originalRequest={pendingRequest}
          onSuccess={handleReAuthSuccess}
        />
      )}
    </>
  );
}
