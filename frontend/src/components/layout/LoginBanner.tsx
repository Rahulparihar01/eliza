/**
 * Login Banner Component
 * 
 * Shows a banner under the header when user logs in,
 * displaying which tenant they're logged into.
 * Auto-dismisses after 3 seconds with smooth animation.
 * 
 * Uses DS Banner component.
 */

import React, { useEffect, useState } from 'react';
import { BuildingOffice2Icon } from '@heroicons/react/24/outline';
import { useAuth } from '../../stores/useAuth';
import { Banner } from '../ui';

export function LoginBanner() {
  const { user, showLoginBanner, setShowLoginBanner } = useAuth();
  const [shouldRender, setShouldRender] = useState(false);

  useEffect(() => {
    if (showLoginBanner && user?.customer_name) {
      // Small delay before showing for smoother appearance
      const timer = setTimeout(() => {
        setShouldRender(true);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [showLoginBanner, user?.customer_name]);

  const handleDismiss = () => {
    setShouldRender(false);
    setShowLoginBanner(false);
  };

  if (!showLoginBanner || !user?.customer_name || !shouldRender) {
    return null;
  }

  return (
    <Banner
      variant="brand"
      icon={<BuildingOffice2Icon className="h-5 w-5" />}
      message={
        <>
          You're logged into{' '}
          <strong className="font-semibold">{user.customer_name}</strong>
        </>
      }
      dismissible={true}
      onDismiss={handleDismiss}
      autoDismiss={3000}
    />
  );
}

export default LoginBanner;
