'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { ReAuthModal } from './ReAuthModal';
import { useSessionGuard } from '@/hooks/useSessionGuard';

interface SessionGuardProviderProps {
  children: React.ReactNode;
}

export function SessionGuardProvider({ children }: SessionGuardProviderProps) {
  const [sessionExpired, setSessionExpired] = useState(false);
  const [pendingRequest, setPendingRequest] = useState<any>(null);

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
      {sessionExpired && pendingRequest && (
        <ReAuthModal
          originalRequest={pendingRequest}
          onSuccess={handleReAuthSuccess}
        />
      )}
    </>
  );
}
