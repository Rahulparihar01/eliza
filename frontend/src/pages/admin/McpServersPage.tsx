/**
 * MCP Servers — Tenant Admin Page
 *
 * Allows tenant admins to manage MCP server configurations.
 * Workspaces is the first applet that supports MCP.
 * Future applets can be added as additional cards.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ServerStackIcon,
  PlusIcon,
  TrashIcon,
  PencilIcon,
  CheckIcon,
  XMarkIcon,
  ClipboardDocumentIcon,
} from '@heroicons/react/24/outline';
import {
  Badge,
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
  Switch,
  Textarea,
} from '../../components/ui';
import { useToasts } from '../../stores/useToasts';

const API_BASE =
  process.env.REACT_APP_API_URL ||
  (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001');

interface MCPConfig {
  id: number;
  customer_id: string;
  server_type: string;
  server_name: string;
  display_name: string | null;
  description: string | null;
  icon_url: string | null;
  is_enabled: boolean;
  allowed_workspace_ids: number[] | null;
  allowed_tool_names: string[] | null;
  enabled_widgets: string[] | null;
  rate_limit_rpm: number;
  rate_limit_rph: number;
  max_concurrent_sessions: number;
  max_async_operations: number;
  oauth_client_id: string | null;
  oauth_redirect_uris: string[];
  server_url: string;
  authorization_url: string;
  token_url: string;
  oauth_token_endpoint_auth_method: string;
}

interface Workspace {
  id: number;
  name: string;
  status: string;
}

const KNOWN_TOOLS = [
  'list_workspaces',
  'select_workspace',
  'list_knowledge_bases',
  'search_documents',
  'chat',
  'ask_question',
  'list_data_connections',
  'get_document',
  'upload_document',
  'trigger_sync',
] as const;

const parseRedirectUris = (value: string): string[] =>
  value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);

export default function McpServersPage() {
  const token = localStorage.getItem('auth_token');
  const { push: addToast } = useToasts();

  const [loading, setLoading] = useState(true);
  const [configs, setConfigs] = useState<MCPConfig[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  // Draft state for create / edit
  const [draft, setDraft] = useState<{
    display_name: string;
    description: string;
    is_enabled: boolean;
    allowed_workspace_ids: number[];
    allowed_tool_names: string[];
    rate_limit_rpm: number;
    rate_limit_rph: number;
    oauth_client_id: string;
    oauth_redirect_uris_text: string;
  }>({
    display_name: '',
    description: '',
    is_enabled: false,
    allowed_workspace_ids: [],
    allowed_tool_names: [],
    rate_limit_rpm: 30,
    rate_limit_rph: 500,
    oauth_client_id: '',
    oauth_redirect_uris_text: '',
  });
  const [showCreate, setShowCreate] = useState(false);

  const headers = useMemo(
    () => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }),
    [token],
  );

  const fetchConfigs = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/v1/mcp/admin/configs`, { headers });
      if (res.ok) setConfigs(await res.json());
    } catch {
      /* non-critical */
    }
  }, [headers]);

  const fetchWorkspaces = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/v1/ragflow/domains`, { headers });
      if (res.ok) {
        const data = await res.json();
        setWorkspaces(data.domains ?? data ?? []);
      }
    } catch {
      /* non-critical */
    }
  }, [headers]);

  useEffect(() => {
    Promise.all([fetchConfigs(), fetchWorkspaces()]).finally(() => setLoading(false));
  }, [fetchConfigs, fetchWorkspaces]);

  const workspaceMap = useMemo(
    () => new Map(workspaces.map((w) => [w.id, w.name])),
    [workspaces],
  );

  const copyValue = useCallback(
    async (label: string, value: string) => {
      try {
        await navigator.clipboard.writeText(value);
        addToast({ kind: 'success', message: `${label} copied` });
      } catch {
        addToast({ kind: 'error', message: `Failed to copy ${label.toLowerCase()}` });
      }
    },
    [addToast],
  );

  // Toggle is_enabled for an existing config
  const handleToggle = async (config: MCPConfig) => {
    try {
      const res = await fetch(`${API_BASE}/v1/mcp/admin/configs/${config.id}/toggle`, {
        method: 'POST',
        headers,
      });
      if (res.ok) {
        const updated: MCPConfig = await res.json();
        setConfigs((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
        addToast({ kind: 'success', message: `MCP server ${updated.is_enabled ? 'enabled' : 'disabled'}` });
      } else {
        addToast({ kind: 'error', message: 'Failed to toggle MCP server' });
      }
    } catch {
      addToast({ kind: 'error', message: 'Failed to toggle MCP server' });
    }
  };

  const startEdit = (config: MCPConfig) => {
    setEditingId(config.id);
    setDraft({
      display_name: config.display_name ?? '',
      description: config.description ?? '',
      is_enabled: config.is_enabled,
      allowed_workspace_ids: config.allowed_workspace_ids ?? [],
      allowed_tool_names: config.allowed_tool_names ?? [],
      rate_limit_rpm: config.rate_limit_rpm,
      rate_limit_rph: config.rate_limit_rph,
      oauth_client_id: config.oauth_client_id ?? '',
      oauth_redirect_uris_text: (config.oauth_redirect_uris ?? []).join('\n'),
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setShowCreate(false);
  };

  const startCreate = () => {
    setShowCreate(true);
    setEditingId(null);
    setDraft({
      display_name: 'Workspaces MCP Server',
      description: 'MCP access to workspace knowledge bases',
      is_enabled: true,
      allowed_workspace_ids: [],
      allowed_tool_names: [],
      rate_limit_rpm: 30,
      rate_limit_rph: 500,
      oauth_client_id: '',
      oauth_redirect_uris_text: '',
    });
  };

  const saveConfig = async () => {
    setSaving(true);
    try {
      if (showCreate) {
        const res = await fetch(`${API_BASE}/v1/mcp/admin/configs`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            server_type: 'applet',
            server_name: 'workspaces',
            display_name: draft.display_name || null,
            description: draft.description || null,
            is_enabled: draft.is_enabled,
            allowed_workspace_ids: draft.allowed_workspace_ids,
            allowed_tool_names: draft.allowed_tool_names.length ? draft.allowed_tool_names : [],
            rate_limit_rpm: draft.rate_limit_rpm,
            rate_limit_rph: draft.rate_limit_rph,
            oauth_client_id: draft.oauth_client_id.trim() || null,
            oauth_redirect_uris: parseRedirectUris(draft.oauth_redirect_uris_text),
          }),
        });
        if (res.ok) {
          addToast({ kind: 'success', message: 'MCP server created' });
          setShowCreate(false);
          await fetchConfigs();
        } else {
          const err = await res.json().catch(() => ({}));
          addToast({ kind: 'error', message: err.detail || 'Failed to create MCP server' });
        }
      } else if (editingId) {
        const res = await fetch(`${API_BASE}/v1/mcp/admin/configs/${editingId}`, {
          method: 'PATCH',
          headers,
          body: JSON.stringify({
            display_name: draft.display_name || null,
            description: draft.description || null,
            is_enabled: draft.is_enabled,
            allowed_workspace_ids: draft.allowed_workspace_ids,
            allowed_tool_names: draft.allowed_tool_names.length ? draft.allowed_tool_names : [],
            rate_limit_rpm: draft.rate_limit_rpm,
            rate_limit_rph: draft.rate_limit_rph,
            oauth_client_id: draft.oauth_client_id.trim() || null,
            oauth_redirect_uris: parseRedirectUris(draft.oauth_redirect_uris_text),
          }),
        });
        if (res.ok) {
          const updated: MCPConfig = await res.json();
          setConfigs((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
          setEditingId(null);
          addToast({ kind: 'success', message: 'MCP server updated' });
        } else {
          const err = await res.json().catch(() => ({}));
          addToast({ kind: 'error', message: err.detail || 'Failed to update MCP server' });
        }
      }
    } catch {
      addToast({ kind: 'error', message: 'Failed to save MCP server' });
    } finally {
      setSaving(false);
    }
  };

  const deleteConfig = async (configId: number) => {
    if (!window.confirm('Delete this MCP server configuration?')) return;
    try {
      const res = await fetch(`${API_BASE}/v1/mcp/admin/configs/${configId}`, {
        method: 'DELETE',
        headers,
      });
      if (res.ok || res.status === 204) {
        setConfigs((prev) => prev.filter((c) => c.id !== configId));
        if (editingId === configId) setEditingId(null);
        addToast({ kind: 'success', message: 'MCP server deleted' });
      } else {
        addToast({ kind: 'error', message: 'Failed to delete MCP server' });
      }
    } catch {
      addToast({ kind: 'error', message: 'Failed to delete MCP server' });
    }
  };

  const toggleWorkspace = (wsId: number) => {
    setDraft((prev) => ({
      ...prev,
      allowed_workspace_ids: prev.allowed_workspace_ids.includes(wsId)
        ? prev.allowed_workspace_ids.filter((id) => id !== wsId)
        : [...prev.allowed_workspace_ids, wsId],
    }));
  };

  const toggleTool = (tool: string) => {
    setDraft((prev) => ({
      ...prev,
      allowed_tool_names: prev.allowed_tool_names.includes(tool)
        ? prev.allowed_tool_names.filter((t) => t !== tool)
        : [...prev.allowed_tool_names, tool],
    }));
  };

  if (loading) {
    return (
      <Page maxWidth="xl">
        <PageBody>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Spinner size="sm" />
            Loading MCP server settings...
          </div>
        </PageBody>
      </Page>
    );
  }

  const isEditing = editingId !== null || showCreate;

  return (
    <Page maxWidth="xl">
      <PageHeader
        title="MCP Servers"
        description="Manage Model Context Protocol (MCP) server configurations. Control which workspaces, tools, and rate limits are exposed to AI agents."
        actions={
          !isEditing ? (
            <Button onClick={startCreate}>
              <PlusIcon className="mr-2 h-4 w-4" />
              Add MCP Server
            </Button>
          ) : undefined
        }
      />
      <PageBody className="space-y-6">
        {/* Create form */}
        {showCreate && (
          <ConfigForm
            title="New MCP Server"
            draft={draft}
            setDraft={setDraft}
            workspaces={workspaces}
            toggleWorkspace={toggleWorkspace}
            toggleTool={toggleTool}
            onSave={saveConfig}
            onCancel={cancelEdit}
            saving={saving}
          />
        )}

        {/* Existing configs */}
        {configs.length === 0 && !showCreate && (
          <Card>
            <CardContent className="py-12 text-center">
              <ServerStackIcon className="mx-auto mb-4 h-12 w-12 text-gray-400 dark:text-gray-500" />
              <h3 className="text-lg font-medium text-charcoal dark:text-gray-100 mb-2">No MCP Servers</h3>
              <p className="text-gray-500 dark:text-gray-400 mb-4">
                Create an MCP server configuration to expose workspaces and tools to AI agents.
              </p>
              <Button onClick={startCreate}>
                <PlusIcon className="mr-2 h-4 w-4" />
                Add MCP Server
              </Button>
            </CardContent>
          </Card>
        )}

        {configs.map((config) =>
          editingId === config.id ? (
            <ConfigForm
              key={config.id}
              title={`Edit: ${config.display_name || config.server_name}`}
              draft={draft}
              setDraft={setDraft}
              workspaces={workspaces}
              toggleWorkspace={toggleWorkspace}
              toggleTool={toggleTool}
              onSave={saveConfig}
              onCancel={cancelEdit}
              saving={saving}
            />
          ) : (
            <ConfigCard
              key={config.id}
              config={config}
              workspaceMap={workspaceMap}
              onToggle={() => handleToggle(config)}
              onEdit={() => startEdit(config)}
              onDelete={() => deleteConfig(config.id)}
              onCopy={copyValue}
              disabled={isEditing}
            />
          ),
        )}
      </PageBody>
    </Page>
  );
}

/* ============================
   Config Card (read-only view)
   ============================ */

function ConfigCard({
  config,
  workspaceMap,
  onToggle,
  onEdit,
  onDelete,
  onCopy,
  disabled,
}: {
  config: MCPConfig;
  workspaceMap: Map<number, string>;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onCopy: (label: string, value: string) => Promise<void>;
  disabled: boolean;
}) {
  const allowedWs = config.allowed_workspace_ids ?? [];
  const allowedTools = config.allowed_tool_names ?? [];
  const redirectUris = config.oauth_redirect_uris ?? [];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-eliza-red/10">
              <ServerStackIcon className="h-5 w-5 text-eliza-red" />
            </div>
            <div>
              <CardTitle className="flex items-center gap-2">
                {config.display_name || config.server_name}
                <Badge variant={config.is_enabled ? 'success' : 'default'}>
                  {config.is_enabled ? 'Enabled' : 'Disabled'}
                </Badge>
              </CardTitle>
              <CardDescription>
                {config.description || `Type: ${config.server_type} · Name: ${config.server_name}`}
              </CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              checked={config.is_enabled}
              onCheckedChange={onToggle}
              disabled={disabled}
            />
            <Button variant="ghost" size="sm" onClick={onEdit} disabled={disabled}>
              <PencilIcon className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm" onClick={onDelete} disabled={disabled}>
              <TrashIcon className="h-4 w-4 text-red-500" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {/* Workspaces */}
          <div>
            <p className="mb-1 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Workspaces
            </p>
            {allowedWs.length === 0 ? (
              <span className="text-sm text-gray-600 dark:text-gray-300">All workspaces</span>
            ) : (
              <div className="flex flex-wrap gap-1">
                {allowedWs.map((id) => (
                  <Badge key={id} variant="outline" className="text-xs">
                    {workspaceMap.get(id) || `#${id}`}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Tools */}
          <div>
            <p className="mb-1 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Tools
            </p>
            {allowedTools.length === 0 ? (
              <span className="text-sm text-gray-600 dark:text-gray-300">All tools</span>
            ) : (
              <span className="text-sm text-gray-600 dark:text-gray-300">{allowedTools.length} tools</span>
            )}
          </div>

          {/* Rate Limits */}
          <div>
            <p className="mb-1 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Rate Limits
            </p>
            <span className="text-sm text-gray-600 dark:text-gray-300">
              {config.rate_limit_rpm} rpm · {config.rate_limit_rph} rph
            </span>
          </div>

          {/* Sessions */}
          <div>
            <p className="mb-1 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Concurrency
            </p>
            <span className="text-sm text-gray-600 dark:text-gray-300">
              {config.max_concurrent_sessions} sessions · {config.max_async_operations} async ops
            </span>
          </div>
        </div>

        <div className="mt-6 border-t border-gray-200 pt-4 dark:border-dark-border">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-charcoal dark:text-gray-100">Connection Details</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Use these values when adding the connector in ChatGPT or Claude.
              </p>
            </div>
            <Badge variant="outline" className="text-xs">
              No client secret required
            </Badge>
          </div>

          <div className="space-y-3">
            <ConnectionDetailRow label="MCP Server URL" value={config.server_url} onCopy={onCopy} />
            <ConnectionDetailRow label="Authorization URL" value={config.authorization_url} onCopy={onCopy} />
            <ConnectionDetailRow label="Token URL" value={config.token_url} onCopy={onCopy} />
            {config.oauth_client_id ? (
              <ConnectionDetailRow label="OAuth Client ID" value={config.oauth_client_id} onCopy={onCopy} />
            ) : null}
            {redirectUris.length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                  Registered Redirect URIs
                </p>
                <div className="space-y-2">
                  {redirectUris.map((uri) => (
                    <ConnectionDetailRow key={uri} label="Redirect URI" value={uri} onCopy={onCopy} />
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-amber-600 dark:text-amber-400">
                Add the callback URL from ChatGPT or Claude to the redirect URI list before testing OAuth.
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ConnectionDetailRow({
  label,
  value,
  onCopy,
}: {
  label: string;
  value: string;
  onCopy: (label: string, value: string) => Promise<void>;
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-dark-border dark:bg-dark-surface">
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
          {label}
        </p>
        <Button variant="ghost" size="sm" onClick={() => void onCopy(label, value)}>
          <ClipboardDocumentIcon className="mr-1 h-4 w-4" />
          Copy
        </Button>
      </div>
      <code className="block overflow-x-auto whitespace-nowrap text-xs text-charcoal dark:text-gray-100">
        {value}
      </code>
    </div>
  );
}

/* ============================
   Config Form (create / edit)
   ============================ */

function ConfigForm({
  title,
  draft,
  setDraft,
  workspaces,
  toggleWorkspace,
  toggleTool,
  onSave,
  onCancel,
  saving,
}: {
  title: string;
  draft: {
    display_name: string;
    description: string;
    is_enabled: boolean;
    allowed_workspace_ids: number[];
    allowed_tool_names: string[];
    rate_limit_rpm: number;
    rate_limit_rph: number;
    oauth_client_id: string;
    oauth_redirect_uris_text: string;
  };
  setDraft: React.Dispatch<React.SetStateAction<typeof draft>>;
  workspaces: Workspace[];
  toggleWorkspace: (id: number) => void;
  toggleTool: (tool: string) => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
}) {
  return (
    <Card className="border-eliza-red/30">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <ServerStackIcon className="h-5 w-5 text-eliza-red" />
            {title}
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={onCancel} disabled={saving}>
              <XMarkIcon className="mr-1 h-4 w-4" />
              Cancel
            </Button>
            <Button size="sm" onClick={onSave} disabled={saving}>
              {saving ? (
                <Spinner size="sm" className="mr-2" />
              ) : (
                <CheckIcon className="mr-1 h-4 w-4" />
              )}
              Save
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Basic Info */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Display Name</Label>
            <Input
              value={draft.display_name}
              onChange={(e) => setDraft((d) => ({ ...d, display_name: e.target.value }))}
              placeholder="Workspaces MCP Server"
            />
          </div>
          <div className="space-y-2">
            <Label>Description</Label>
            <Input
              value={draft.description}
              onChange={(e) => setDraft((d) => ({ ...d, description: e.target.value }))}
              placeholder="MCP access to workspace knowledge bases"
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>OAuth Client ID</Label>
            <Input
              value={draft.oauth_client_id}
              onChange={(e) => setDraft((d) => ({ ...d, oauth_client_id: e.target.value }))}
              placeholder="Optional. Leave blank to auto-generate on create"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Shown in the connection details so admins can paste it into ChatGPT or Claude if needed.
            </p>
          </div>

          <div className="space-y-2">
            <Label>OAuth Redirect URIs</Label>
            <Textarea
              rows={4}
              value={draft.oauth_redirect_uris_text}
              onChange={(e) => setDraft((d) => ({ ...d, oauth_redirect_uris_text: e.target.value }))}
              placeholder={'Paste one callback URL per line\nhttps://chatgpt.com/connector/oauth/callback\nhttps://claude.ai/api/mcp/auth_callback'}
            />
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Paste the callback URL supplied by ChatGPT or Claude. Client secrets are not used yet.
            </p>
          </div>
        </div>

        {/* Enabled */}
        <div className="flex items-center gap-3">
          <Switch
            checked={draft.is_enabled}
            onCheckedChange={(v) => setDraft((d) => ({ ...d, is_enabled: v }))}
          />
          <Label className="cursor-pointer">Enabled</Label>
        </div>

        {/* Workspace Selection */}
        <div>
          <Label className="mb-2 block">Allowed Workspaces</Label>
          <p className="mb-3 text-xs text-gray-500 dark:text-gray-400">
            Select which workspaces are accessible via MCP. Leave empty to allow all.
          </p>
          {workspaces.length === 0 ? (
            <p className="text-sm text-gray-400">No workspaces found</p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {workspaces.map((ws) => {
                const selected = draft.allowed_workspace_ids.includes(ws.id);
                return (
                  <button
                    key={ws.id}
                    type="button"
                    onClick={() => toggleWorkspace(ws.id)}
                    className={`
                      flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors
                      ${
                        selected
                          ? 'border-eliza-red/40 bg-eliza-red/5 text-charcoal dark:text-white'
                          : 'border-gray-200 dark:border-dark-border text-gray-600 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-500'
                      }
                    `}
                  >
                    <div
                      className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border text-xs ${
                        selected
                          ? 'border-eliza-red bg-eliza-red text-white'
                          : 'border-gray-300 dark:border-gray-600'
                      }`}
                    >
                      {selected && <CheckIcon className="h-3 w-3" />}
                    </div>
                    <span className="truncate">{ws.name}</span>
                  </button>
                );
              })}
            </div>
          )}
          {draft.allowed_workspace_ids.length === 0 && workspaces.length > 0 && (
            <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
              No workspaces selected — all workspaces will be accessible.
            </p>
          )}
        </div>

        {/* Tool Selection */}
        <div>
          <Label className="mb-2 block">Allowed Tools</Label>
          <p className="mb-3 text-xs text-gray-500 dark:text-gray-400">
            Select which MCP tools are available. Leave empty to allow all tools.
          </p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {KNOWN_TOOLS.map((tool) => {
              const selected = draft.allowed_tool_names.includes(tool);
              return (
                <button
                  key={tool}
                  type="button"
                  onClick={() => toggleTool(tool)}
                  className={`
                    flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors
                    ${
                      selected
                        ? 'border-eliza-red/40 bg-eliza-red/5 text-charcoal dark:text-white'
                        : 'border-gray-200 dark:border-dark-border text-gray-600 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-500'
                    }
                  `}
                >
                  <div
                    className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border text-xs ${
                      selected
                        ? 'border-eliza-red bg-eliza-red text-white'
                        : 'border-gray-300 dark:border-gray-600'
                    }`}
                  >
                    {selected && <CheckIcon className="h-3 w-3" />}
                  </div>
                  <span className="font-mono text-xs">{tool}</span>
                </button>
              );
            })}
          </div>
          {draft.allowed_tool_names.length === 0 && (
            <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
              No tools selected — all tools will be available.
            </p>
          )}
        </div>

        {/* Rate Limits */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Requests per minute</Label>
            <Input
              type="number"
              min={1}
              max={10000}
              value={draft.rate_limit_rpm}
              onChange={(e) => setDraft((d) => ({ ...d, rate_limit_rpm: Number(e.target.value) || 30 }))}
            />
          </div>
          <div className="space-y-2">
            <Label>Requests per hour</Label>
            <Input
              type="number"
              min={1}
              max={100000}
              value={draft.rate_limit_rph}
              onChange={(e) => setDraft((d) => ({ ...d, rate_limit_rph: Number(e.target.value) || 500 }))}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
