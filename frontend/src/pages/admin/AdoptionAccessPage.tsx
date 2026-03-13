/**
 * Adoption Access Page
 * 
 * Allows tenant admins to view and manage adoption data sharing grants.
 * Shows both inbound (we can view) and outbound (they can view) grants.
 * 
 * Tenant admins can toggle grants on/off but cannot create new ones.
 * Only platform admins can create new grants.
 */

import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowDownTrayIcon,
  ArrowUpTrayIcon,
  BuildingOffice2Icon,
  ChartBarIcon,
  CheckCircleIcon,
  XCircleIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import Layout from '../../components/layout/Layout';
import { AXIOS_INSTANCE } from '../../services/api-client';
import {
  Alert,
  Badge,
  Spinner,
  Switch,
  Panel,
  PanelHeader,
  PanelTitle,
  PanelDescription,
  PanelBody,
  SectionHeader,
} from '../../components/ui';

interface AdoptionGrantInfo {
  id: number;
  customer_id: string;
  customer_name: string | null;
  is_enabled: boolean;
  share_level: string;
  granted_at: string;
  expires_at: string | null;
}

interface TenantAdoptionAccessResponse {
  inbound_grants: AdoptionGrantInfo[];
  outbound_grants: AdoptionGrantInfo[];
}

interface AdoptionAccessPageProps {
  embedded?: boolean;
  showHeader?: boolean;
}

export function AdoptionAccessPage({ embedded = false, showHeader = true }: AdoptionAccessPageProps) {
  const queryClient = useQueryClient();

  // Fetch adoption access data
  const { data, isLoading, error } = useQuery({
    queryKey: ['adoption-access'],
    queryFn: async () => {
      const response = await AXIOS_INSTANCE.get<TenantAdoptionAccessResponse>(
        '/api/v1/admin/adoption-access'
      );
      return response.data;
    },
  });

  // Toggle grant mutation
  const toggleGrant = useMutation({
    mutationFn: async ({ grantId, isEnabled }: { grantId: number; isEnabled: boolean }) => {
      await AXIOS_INSTANCE.put(`/api/v1/admin/adoption-access/${grantId}`, {
        is_enabled: isEnabled,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adoption-access'] });
    },
  });

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const GrantCard = ({
    grant,
    type,
  }: {
    grant: AdoptionGrantInfo;
    type: 'inbound' | 'outbound';
  }) => {
    const isInbound = type === 'inbound';
    const isPending = toggleGrant.isPending && toggleGrant.variables?.grantId === grant.id;

    return (
      <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-dark-surface-2/60 rounded-lg border border-gray-200 dark:border-dark-border hover:border-eliza-red/30 transition-colors">
        <div className="flex items-center gap-4">
          <div className={`p-2 rounded-lg ${isInbound ? 'bg-eliza-red/10' : 'bg-sky-100 dark:bg-sky-900/30'}`}>
            <BuildingOffice2Icon className={`h-5 w-5 ${isInbound ? 'text-eliza-red' : 'text-sky-600 dark:text-sky-400'}`} />
          </div>
          <div>
            <div className="font-medium text-charcoal dark:text-gray-100">
              {grant.customer_name || grant.customer_id}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-2">
              <span className="font-mono">{grant.customer_id}</span>
              <span>•</span>
              <span>Since {formatDate(grant.granted_at)}</span>
              {grant.expires_at && (
                <>
                  <span>•</span>
                  <span className="text-amber-600 dark:text-amber-400">Expires {formatDate(grant.expires_at)}</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Status Badge */}
          <Badge variant={grant.is_enabled ? 'success' : 'secondary'} className="inline-flex items-center gap-1.5">
            {grant.is_enabled ? <CheckCircleIcon className="h-3.5 w-3.5" /> : <XCircleIcon className="h-3.5 w-3.5" />}
            {grant.is_enabled ? 'Active' : 'Disabled'}
          </Badge>

          {/* Toggle */}
          <Switch
            checked={grant.is_enabled}
            onCheckedChange={(checked) => toggleGrant.mutate({ grantId: grant.id, isEnabled: checked })}
            disabled={isPending}
          />
        </div>
      </div>
    );
  };

  const EmptyState = ({ type }: { type: 'inbound' | 'outbound' }) => {
    const isInbound = type === 'inbound';
    return (
      <div className="text-center py-8 px-4 bg-gray-50 dark:bg-dark-surface-2/40 rounded-lg border border-dashed border-gray-200 dark:border-dark-border">
        <div className={`mx-auto w-12 h-12 rounded-full flex items-center justify-center ${
          isInbound ? 'bg-eliza-red/10' : 'bg-sky-100 dark:bg-sky-900/30'
        }`}>
          {isInbound ? (
            <ArrowDownTrayIcon className="h-6 w-6 text-eliza-red" />
          ) : (
            <ArrowUpTrayIcon className="h-6 w-6 text-sky-600 dark:text-sky-400" />
          )}
        </div>
        <h4 className="mt-3 text-sm font-medium text-charcoal dark:text-gray-100">
          No {isInbound ? 'Inbound' : 'Outbound'} Grants
        </h4>
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400 max-w-xs mx-auto">
          {isInbound
            ? "No other tenants have shared their adoption data with you."
            : "You haven't shared your adoption data with any other tenants."}
        </p>
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
          Contact your platform administrator to set up data sharing.
        </p>
      </div>
    );
  };

  const content = (
    <div className={`${embedded ? '' : 'h-full overflow-y-auto bg-gray-50 dark:bg-dark-bg'}`}>
      {error ? (
        <div className="p-6">
          <Alert variant="error">Failed to load adoption access data.</Alert>
        </div>
      ) : (
        <>
        <div className={`${embedded ? 'space-y-6' : 'max-w-4xl mx-auto px-6 py-8 space-y-8'}`}>
          {showHeader && (
            <SectionHeader
              title="Adoption Data Sharing"
              description="Manage how adoption metrics are shared with other organizations"
              icon={<ChartBarIcon className="h-5 w-5 text-eliza-red" />}
            />
          )}

          {/* Info Banner */}
          <div className="flex items-start gap-3 p-4 bg-sky-50 dark:bg-sky-900/20 border border-sky-200 dark:border-sky-800 rounded-lg">
            <InformationCircleIcon className="h-5 w-5 text-sky-600 dark:text-sky-400 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-charcoal dark:text-gray-100">
              <p className="font-medium">About Adoption Data Sharing</p>
              <p className="text-gray-500 dark:text-gray-400 mt-1">
                Adoption data sharing allows organizations to view each other's AI usage metrics.
                You can enable or disable existing grants below. To create new sharing relationships,
                please contact your platform administrator.
              </p>
            </div>
          </div>

          {/* Inbound Grants */}
          <Panel>
            <PanelHeader className="flex items-center gap-3">
              <div className="p-2 bg-eliza-red/10 rounded-lg">
                <ArrowDownTrayIcon className="h-5 w-5 text-eliza-red" />
              </div>
              <div>
                <PanelTitle>Inbound Access</PanelTitle>
                <PanelDescription>Tenants whose adoption data you can view</PanelDescription>
              </div>
              {data && data.inbound_grants.length > 0 && (
                <span className="ml-auto px-2.5 py-1 bg-eliza-red/10 text-eliza-red text-xs font-medium rounded-full">
                  {data.inbound_grants.length} tenant{data.inbound_grants.length !== 1 ? 's' : ''}
                </span>
              )}
            </PanelHeader>
            <PanelBody className="p-4 space-y-3">
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Spinner />
                </div>
              ) : data && data.inbound_grants.length > 0 ? (
                data.inbound_grants.map((grant) => (
                  <GrantCard key={grant.id} grant={grant} type="inbound" />
                ))
              ) : (
                <EmptyState type="inbound" />
              )}
            </PanelBody>
          </Panel>

          {/* Outbound Grants */}
          <Panel>
            <PanelHeader className="flex items-center gap-3">
              <div className="p-2 bg-sky-100 dark:bg-sky-900/30 rounded-lg">
                <ArrowUpTrayIcon className="h-5 w-5 text-sky-600 dark:text-sky-400" />
              </div>
              <div>
                <PanelTitle>Outbound Access</PanelTitle>
                <PanelDescription>Tenants who can view your adoption data</PanelDescription>
              </div>
              {data && data.outbound_grants.length > 0 && (
                <span className="ml-auto px-2.5 py-1 bg-sky-100 dark:bg-sky-900/30 text-sky-600 dark:text-sky-400 text-xs font-medium rounded-full">
                  {data.outbound_grants.length} tenant{data.outbound_grants.length !== 1 ? 's' : ''}
                </span>
              )}
            </PanelHeader>
            <PanelBody className="p-4 space-y-3">
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Spinner />
                </div>
              ) : data && data.outbound_grants.length > 0 ? (
                data.outbound_grants.map((grant) => (
                  <GrantCard key={grant.id} grant={grant} type="outbound" />
                ))
              ) : (
                <EmptyState type="outbound" />
              )}
            </PanelBody>
          </Panel>
        </div>
        </>
      )}
    </div>
  );

  if (embedded) {
    return content;
  }

  return <Layout>{content}</Layout>;
}

export default AdoptionAccessPage;

