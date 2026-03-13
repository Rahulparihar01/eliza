/**
 * Accept Invite Page - Eliza Forge
 * 
 * Registration page for users who receive an invite link.
 * Following the Design System (DESIGN_SYSTEM.md)
 */

import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { AXIOS_INSTANCE } from '../../services/api-client';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Button,
  Input,
  Label,
  Alert,
  Spinner,
} from '../../components/ui';
import {
  EyeIcon,
  EyeSlashIcon,
  BuildingOffice2Icon,
  ArrowRightIcon,
} from '@heroicons/react/24/outline';
import { CheckCircleIcon as CheckCircleSolid } from '@heroicons/react/24/solid';

interface InviteInfo {
  email: string;
  full_name: string | null;
  customer_name: string;
  customer_id: string;
  is_valid: boolean;
  expires_at: string;
  user_exists: boolean;
}

export default function AcceptInvitePage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [inviteInfo, setInviteInfo] = useState<InviteInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [isExistingUser, setIsExistingUser] = useState(false);

  // Fetch invite info on mount
  useEffect(() => {
    if (!token) {
      setError('Invalid invite link. No token provided.');
      setLoading(false);
      return;
    }

    const fetchInviteInfo = async () => {
      try {
        const response = await AXIOS_INSTANCE.get(`/v1/auth/invite/${token}`);
        setInviteInfo(response.data);
      } catch (err: any) {
        const errorMessage = err.response?.data?.detail || 'Invalid or expired invite link';
        setError(errorMessage);
      } finally {
        setLoading(false);
      }
    };

    fetchInviteInfo();
  }, [token]);

  // Password validation
  const validatePassword = () => {
    if (password.length < 8) {
      setPasswordError('Password must be at least 8 characters');
      return false;
    }
    if (password !== confirmPassword) {
      setPasswordError('Passwords do not match');
      return false;
    }
    setPasswordError(null);
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validatePassword()) return;
    if (!token) return;

    setSubmitting(true);
    setError(null);

    try {
      const response = await AXIOS_INSTANCE.post('/v1/auth/invite/accept', {
        token,
        password,
        confirm_password: confirmPassword,
      });
      setSuccessMessage(response.data.message || 'Account created successfully!');
      const isExisting = response.data.message?.includes('added to') || 
                         response.data.message?.includes('already a member');
      setIsExistingUser(isExisting);
      setSuccess(true);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to create account';
      if (errorMessage.includes('already a member') || errorMessage.includes('added to')) {
        setSuccessMessage(errorMessage);
        setIsExistingUser(true);
        setSuccess(true);
      } else {
        setError(errorMessage);
      }
    } finally {
      setSubmitting(false);
    }
  };

  // Handle accept for existing users (no password needed)
  const handleAcceptExisting = async () => {
    if (!token) return;

    setSubmitting(true);
    setError(null);

    try {
      const response = await AXIOS_INSTANCE.post('/v1/auth/invite/accept-existing', {
        token,
      });
      setSuccessMessage(response.data.message || `You've been added to ${inviteInfo?.customer_name}!`);
      setIsExistingUser(true);
      setSuccess(true);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to accept invite';
      if (errorMessage.includes('already a member')) {
        setSuccessMessage(errorMessage);
        setIsExistingUser(true);
        setSuccess(true);
      } else {
        setError(errorMessage);
      }
    } finally {
      setSubmitting(false);
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-dark-bg flex items-center justify-center">
        <div className="text-center">
          <Spinner size="xl" variant="primary" />
          <p className="mt-4 text-gray-500 dark:text-gray-400">Validating your invite...</p>
        </div>
      </div>
    );
  }

  // Success state
  if (success) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-dark-bg flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <Card>
            <CardContent className="pt-8 pb-8 text-center">
              {/* Success icon */}
              <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                <CheckCircleSolid className="w-8 h-8 text-green-600 dark:text-green-400" />
              </div>

              <h1 className="font-title text-h2 text-charcoal dark:text-gray-100 mb-3">
                {isExistingUser ? 'Welcome Aboard!' : 'You\'re All Set!'}
              </h1>
              
              <p className="text-gray-500 dark:text-gray-400 mb-6">
                {successMessage || (isExistingUser 
                  ? `You've been added to ${inviteInfo?.customer_name}. Switch organizations anytime from your dashboard.`
                  : 'Your account is ready. Sign in to start exploring your new workspace.'
                )}
              </p>

              {isExistingUser && (
                <Alert variant="info" className="mb-6 text-left">
                  <span className="font-medium">Tip:</span> Use the organization dropdown in the header to switch between your workspaces.
                </Alert>
              )}

              <Link to="/login">
                <Button variant="brand" className="w-full">
                  Continue to Sign In
                  <ArrowRightIcon className="w-4 h-4" />
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // Error state (invalid/expired invite)
  if (error && !inviteInfo) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-dark-bg flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <Card>
            <CardContent className="pt-8 pb-8 text-center">
              {/* Error icon */}
              <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                <svg className="w-8 h-8 text-red-600 dark:text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>

              <h1 className="font-title text-h2 text-charcoal dark:text-gray-100 mb-3">
                Invite Not Found
              </h1>
              <p className="text-gray-500 dark:text-gray-400 mb-6">{error}</p>

              <Link to="/login">
                <Button variant="secondary" className="w-full">
                  Go to Login
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // Main form
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-dark-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Card>
          {/* Header with organization info */}
          <CardHeader className="text-center border-b border-gray-100 dark:border-dark-border/30 pb-6">
            <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-eliza-red/10 flex items-center justify-center">
              <BuildingOffice2Icon className="w-7 h-7 text-eliza-red" />
            </div>
            <CardDescription className="text-gray-500 dark:text-gray-400 mb-1">
              You've been invited to join
            </CardDescription>
            <CardTitle>{inviteInfo?.customer_name}</CardTitle>
          </CardHeader>

          {/* Existing User Flow - No password needed */}
          {inviteInfo?.user_exists ? (
            <CardContent className="pt-6 space-y-6">
              {/* Info banner */}
              <Alert variant="success">
                <span className="font-medium">Good news!</span> You already have an account with{' '}
                <span className="font-medium">{inviteInfo.email}</span>. 
                Just click below to join this organization.
              </Alert>

              {/* Email (read-only) */}
              <div className="space-y-2">
                <Label>Your Account</Label>
                <Input
                  type="email"
                  value={inviteInfo?.email || ''}
                  disabled
                  className="bg-gray-50 dark:bg-dark-surface-2"
                />
              </div>

              {/* Error message */}
              {error && (
                <Alert variant="error">{error}</Alert>
              )}

              {/* Accept button */}
              <Button
                type="button"
                variant="brand"
                onClick={handleAcceptExisting}
                disabled={submitting}
                className="w-full"
              >
                {submitting ? (
                  <>
                    <Spinner size="sm" variant="white" />
                    Joining...
                  </>
                ) : (
                  `Join ${inviteInfo?.customer_name}`
                )}
              </Button>

              <p className="text-center text-sm text-gray-500 dark:text-gray-400">
                You can switch between workspaces anytime using the header dropdown.
              </p>
            </CardContent>
          ) : (
            /* New User Flow - Password required */
            <CardContent className="pt-6">
              <form onSubmit={handleSubmit} className="space-y-5">
                {/* Email (read-only) */}
                <div className="space-y-2">
                  <Label>Email</Label>
                  <Input
                    type="email"
                    value={inviteInfo?.email || ''}
                    disabled
                    className="bg-gray-50 dark:bg-dark-surface-2"
                  />
                </div>

                {/* Full Name (if provided) */}
                {inviteInfo?.full_name && (
                  <div className="space-y-2">
                    <Label>Name</Label>
                    <Input
                      type="text"
                      value={inviteInfo.full_name}
                      disabled
                      className="bg-gray-50 dark:bg-dark-surface-2"
                    />
                  </div>
                )}

                {/* Password */}
                <div className="space-y-2">
                  <Label htmlFor="password">Create Password</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Create a secure password"
                      required
                      minLength={8}
                      className="pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    >
                      {showPassword ? <EyeSlashIcon className="w-5 h-5" /> : <EyeIcon className="w-5 h-5" />}
                    </button>
                  </div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Minimum 8 characters</p>
                </div>

                {/* Confirm Password */}
                <div className="space-y-2">
                  <Label htmlFor="confirmPassword">Confirm Password</Label>
                  <div className="relative">
                    <Input
                      id="confirmPassword"
                      type={showConfirmPassword ? 'text' : 'password'}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Re-enter your password"
                      required
                      className="pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    >
                      {showConfirmPassword ? <EyeSlashIcon className="w-5 h-5" /> : <EyeIcon className="w-5 h-5" />}
                    </button>
                  </div>
                </div>

                {/* Error message */}
                {(passwordError || error) && (
                  <Alert variant="error">{passwordError || error}</Alert>
                )}

                {/* Submit button */}
                <Button
                  type="submit"
                  variant="brand"
                  disabled={submitting || !password || !confirmPassword}
                  className="w-full"
                >
                  {submitting ? (
                    <>
                      <Spinner size="sm" variant="white" />
                      Creating Account...
                    </>
                  ) : (
                    <>
                      Create Account
                      <ArrowRightIcon className="w-4 h-4" />
                    </>
                  )}
                </Button>

                {/* Login link */}
                <p className="text-center text-sm text-gray-500 dark:text-gray-400">
                  Already have an account?{' '}
                  <Link to="/login" className="text-eliza-red hover:underline font-medium">
                    Sign in
                  </Link>
                </p>
              </form>
            </CardContent>
          )}
        </Card>

        {/* Footer branding */}
        <div className="mt-6 text-center">
          <p className="text-sm text-gray-400 dark:text-gray-500">
            Powered by Eliza Forge
          </p>
        </div>
      </div>
    </div>
  );
}
