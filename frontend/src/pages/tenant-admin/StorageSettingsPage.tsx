import React, { useEffect, useState } from 'react';
import { CloudIcon, KeyIcon } from '@heroicons/react/24/outline';
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Page,
  PageBody,
  PageHeader,
  Spinner,
  Badge,
} from '../../components/ui';
import { useToasts } from '../../stores/useToasts';

type StorageBackend = 's3' | 'minio';

interface TenantStorageSettings {
  backend?: StorageBackend | null;
  bucket?: string | null;
  region?: string | null;
  endpoint_url?: string | null;
  path_prefix?: string | null;
  force_path_style: boolean;
  default_local_source_path?: string | null;
  has_credentials: boolean;
}

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001');

export default function StorageSettingsPage() {
  const token = localStorage.getItem('auth_token');
  const { push: addToast } = useToasts();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [backend, setBackend] = useState<StorageBackend>('s3');
  const [bucket, setBucket] = useState('');
  const [region, setRegion] = useState('us-east-1');
  const [endpointUrl, setEndpointUrl] = useState('');
  const [pathPrefix, setPathPrefix] = useState('');
  const [forcePathStyle, setForcePathStyle] = useState(false);
  const [defaultLocalSourcePath, setDefaultLocalSourcePath] = useState('');
  const [accessKeyId, setAccessKeyId] = useState('');
  const [secretAccessKey, setSecretAccessKey] = useState('');
  const [hasCredentials, setHasCredentials] = useState(false);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/v1/tenant-settings/storage`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          throw new Error('Failed to load storage settings');
        }
        const data: TenantStorageSettings = await res.json();
        if (data.backend) setBackend(data.backend);
        setBucket(data.bucket || '');
        setRegion(data.region || 'us-east-1');
        setEndpointUrl(data.endpoint_url || '');
        setPathPrefix(data.path_prefix || '');
        setForcePathStyle(Boolean(data.force_path_style));
        setDefaultLocalSourcePath(data.default_local_source_path || '');
        setHasCredentials(Boolean(data.has_credentials));
      } catch (e) {
        addToast({
          kind: 'error',
          message: e instanceof Error ? e.message : 'Failed to load storage settings',
        });
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [token, addToast]);

  const handleSave = async () => {
    if (!bucket.trim()) {
      addToast({ kind: 'error', message: 'Bucket is required' });
      return;
    }
    if (backend === 'minio' && !endpointUrl.trim()) {
      addToast({ kind: 'error', message: 'Endpoint URL is required for MinIO' });
      return;
    }
    if ((accessKeyId && !secretAccessKey) || (!accessKeyId && secretAccessKey)) {
      addToast({ kind: 'error', message: 'Provide both access key and secret key to rotate credentials' });
      return;
    }

    setIsSaving(true);
    try {
      const payload: Record<string, unknown> = {
        backend,
        bucket: bucket.trim(),
        region: region.trim() || null,
        endpoint_url: endpointUrl.trim() || null,
        path_prefix: pathPrefix.trim() || null,
        force_path_style: backend === 'minio' ? true : forcePathStyle,
        default_local_source_path: defaultLocalSourcePath.trim() || null,
      };
      if (accessKeyId && secretAccessKey) {
        payload.access_key_id = accessKeyId.trim();
        payload.secret_access_key = secretAccessKey.trim();
      }

      const res = await fetch(`${API_BASE}/api/v1/tenant-settings/storage`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to save storage settings');
      }

      const updated: TenantStorageSettings = await res.json();
      setHasCredentials(Boolean(updated.has_credentials));
      setAccessKeyId('');
      setSecretAccessKey('');
      addToast({ kind: 'success', message: 'Storage settings saved' });
    } catch (e) {
      addToast({
        kind: 'error',
        message: e instanceof Error ? e.message : 'Failed to save storage settings',
      });
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <Page maxWidth="xl">
        <PageBody>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Spinner size="sm" />
            Loading storage settings...
          </div>
        </PageBody>
      </Page>
    );
  }

  return (
    <Page maxWidth="xl">
      <PageHeader
        title="Storage Settings"
        description="Configure tenant-level document object storage (S3 or MinIO)"
        actions={
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? <Spinner size="sm" className="mr-2" /> : <CloudIcon className="mr-2 h-4 w-4" />}
            Save Storage Settings
          </Button>
        }
      />
      <PageBody>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CloudIcon className="h-5 w-5 text-eliza-red" />
              Tenant Object Storage
            </CardTitle>
            <CardDescription>
              Knowledge base uploads and local-directory source migrations use this backend.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Backend</Label>
                <select
                  value={backend}
                  onChange={(e) => setBackend(e.target.value as StorageBackend)}
                  className="h-10 w-full rounded-md border border-gray-200 bg-white px-3 text-sm dark:border-dark-border dark:bg-dark-surface-2"
                >
                  <option value="s3">S3</option>
                  <option value="minio">MinIO</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label>Bucket</Label>
                <Input value={bucket} onChange={(e) => setBucket(e.target.value)} placeholder="tenant-documents" />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Region</Label>
                <Input value={region} onChange={(e) => setRegion(e.target.value)} placeholder="us-east-1" />
              </div>
              <div className="space-y-2">
                <Label>Endpoint URL {backend === 'minio' ? '(required)' : '(optional)'}</Label>
                <Input
                  value={endpointUrl}
                  onChange={(e) => setEndpointUrl(e.target.value)}
                  placeholder="https://minio.company.net"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Path Prefix</Label>
                <Input
                  value={pathPrefix}
                  onChange={(e) => setPathPrefix(e.target.value)}
                  placeholder="rag/workspaces"
                />
              </div>
              <div className="space-y-2">
                <Label>Default Local Source Path</Label>
                <Input
                  value={defaultLocalSourcePath}
                  onChange={(e) => setDefaultLocalSourcePath(e.target.value)}
                  placeholder="/imports/hr/"
                />
              </div>
            </div>

            {backend === 's3' && (
              <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={forcePathStyle}
                  onChange={(e) => setForcePathStyle(e.target.checked)}
                />
                Force path-style URLs
              </label>
            )}

            <div className="rounded-lg border border-gray-200 p-4 dark:border-dark-border">
              <div className="mb-2 flex items-center gap-2">
                <KeyIcon className="h-4 w-4 text-gray-500" />
                <span className="text-sm font-medium text-charcoal dark:text-white">Credentials</span>
                {hasCredentials ? <Badge variant="success">Configured</Badge> : <Badge variant="warning">Missing</Badge>}
              </div>
              <p className="mb-3 text-xs text-gray-500 dark:text-gray-400">
                Existing credentials are never returned. Fill both fields only when rotating keys.
              </p>
              <div className="grid gap-4 md:grid-cols-2">
                <Input
                  value={accessKeyId}
                  onChange={(e) => setAccessKeyId(e.target.value)}
                  placeholder="Access key ID"
                />
                <Input
                  type="password"
                  value={secretAccessKey}
                  onChange={(e) => setSecretAccessKey(e.target.value)}
                  placeholder="Secret access key"
                />
              </div>
            </div>
          </CardContent>
        </Card>
      </PageBody>
    </Page>
  );
}
