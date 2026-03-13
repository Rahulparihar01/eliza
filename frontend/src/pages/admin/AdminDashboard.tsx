/**
 * Admin Dashboard Component
 * Overview of system health and statistics
 * 
 * NOTE: This component is temporarily disabled until admin API endpoints
 * are added to the OpenAPI specification and hooks are generated.
 */

import React from 'react';

export function AdminDashboard() {
  return (
    <div className="container mx-auto p-6">
      <div className="bg-surface rounded-lg shadow-lg p-8 text-center">
        <h1 className="text-2xl font-bold text-text-primary mb-4">Admin Dashboard</h1>
        <p className="text-text-secondary mb-4">
          This feature is currently being updated to use the latest API specifications.
        </p>
        <p className="text-sm text-muted">
          The admin API endpoints need to be added to the OpenAPI spec for auto-generated types.
        </p>
      </div>
    </div>
  );
}
