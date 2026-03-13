import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Card,
  CardContent,
  Button,
  Spinner,
} from '../../components/ui';
import { useAuth } from '../../contexts/AuthContext';

function getHashParams(): URLSearchParams {
  const rawHash = window.location.hash.startsWith('#')
    ? window.location.hash.slice(1)
    : window.location.hash;
  return new URLSearchParams(rawHash);
}

const CALLBACK_TIMEOUT_MS = 15_000;

export default function SSOCallbackPage() {
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  const [error, setError] = useState<string | null>(null);

  // Stable ref so the effect doesn't re-run when AuthProvider re-renders
  // (refreshUser is not memoized, so its identity changes every render).
  const refreshUserRef = useRef(refreshUser);
  refreshUserRef.current = refreshUser;

  useEffect(() => {
    let cancelled = false;

    const finalizeLogin = async () => {
      const hashParams = getHashParams();
      const searchParams = new URLSearchParams(window.location.search);

      const errorMessage = hashParams.get('error') || searchParams.get('message');
      if (errorMessage) {
        if (!cancelled) setError(errorMessage);
        return;
      }

      const accessToken = hashParams.get('access_token');
      const refreshTokenValue = hashParams.get('refresh_token');

      if (accessToken && refreshTokenValue) {
        localStorage.setItem('auth_token', accessToken);
        localStorage.setItem('refresh_token', refreshTokenValue);
        window.history.replaceState({}, '', '/auth/sso/callback');
      }

      const storedToken = localStorage.getItem('auth_token');
      if (!storedToken) {
        if (!cancelled) setError('SSO login did not return valid tokens.');
        return;
      }

      try {
        await refreshUserRef.current();
      } catch (e: any) {
        console.warn('SSO callback: user profile refresh failed', e?.message || e);
      }

      if (!cancelled) {
        navigate('/home', { replace: true });
      }
    };

    finalizeLogin();

    const timeout = setTimeout(() => {
      if (!cancelled) {
        setError(
          'SSO login is taking too long. Your tokens may be invalid or the server is unreachable.',
        );
      }
    }, CALLBACK_TIMEOUT_MS);

    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  // navigate is stable (React Router guarantees this). refreshUser is
  // captured via ref to avoid re-triggering the effect on every AuthProvider render.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigate]);

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-dark-bg flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <Card>
            <CardContent className="pt-8 pb-8 text-center space-y-4">
              <h1 className="font-title text-h2 text-charcoal dark:text-gray-100">
                SSO Login Failed
              </h1>
              <p className="text-gray-500 dark:text-gray-400">{error}</p>
              <div className="space-y-2">
                <Link to="/login">
                  <Button className="w-full">Back to Login</Button>
                </Link>
                <button
                  type="button"
                  className="text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 underline"
                  onClick={() => {
                    localStorage.removeItem('auth_token');
                    localStorage.removeItem('refresh_token');
                    window.location.href = '/login';
                  }}
                >
                  Clear session &amp; return to login
                </button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-dark-bg flex items-center justify-center p-4">
      <div className="text-center">
        <Spinner size="xl" variant="primary" />
        <p className="mt-4 text-gray-500 dark:text-gray-400">
          Completing SSO login...
        </p>
        <button
          type="button"
          className="mt-6 text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 underline"
          onClick={() => {
            localStorage.removeItem('auth_token');
            localStorage.removeItem('refresh_token');
            window.location.href = '/login';
          }}
        >
          Cancel &amp; return to login
        </button>
      </div>
    </div>
  );
}
