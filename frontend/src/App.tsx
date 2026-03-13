/**
 * Main App Component - Eliza Forge
 * 
 * Root application component with routing, authentication, and global providers
 */

import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { NavigationProvider } from './contexts/NavigationContext';
import { useUI } from './stores/useUI';
import { useTheme } from './stores/useTheme';

// Pages
import LoginPage from './pages/auth/LoginPage';
import AcceptInvitePage from './pages/auth/AcceptInvitePage';
import SSOCallbackPage from './pages/auth/SSOCallbackPage';
import AdminSettingsPage from './pages/admin/AdminSettingsPage';
import McpServersPage from './pages/admin/McpServersPage';
import { ResumeParsingTestPage } from './pages/admin/ResumeParsingTestPage';
import DocumentLibrary from './pages/company-data/DocumentLibrary';
import EmployeesOverview from './pages/caylent/EmployeesOverview';
import BusinessIntelligenceQA from './pages/business-intelligence/BusinessIntelligenceQA';
// MyInsights removed - replaced with HomePage
import DataAnalystPage from './pages/data-analyst/DataAnalystPage';
import { AgentConfigurationPage } from './pages/agent-configuration/AgentConfigurationPage';
import SowAutomationPage from './pages/sow/SowAutomationPage';
import ContentResearchPage from './pages/content-research/ContentResearchPage';
import TinyModelStudioPage from './pages/tiny-model-studio/TinyModelStudioPage';
import { DataConnectionsPage } from './pages/data-connections/DataConnectionsPage';
// TalentIntelligencePage removed - functionality moved to Analysis Config
import { TalentAnalysisHistoryPage } from './pages/ml-talent/TalentAnalysisHistoryPage';
import CandidateOutreachPage from './pages/talent-intelligence/CandidateOutreachPage';
import EmailTemplatesPage from './pages/talent-intelligence/EmailTemplatesPage';
import EmailTemplateEditorPage from './pages/talent-intelligence/EmailTemplateEditorPage';
// TalentFeedbackPage removed - feedback is now a slide-in panel from the header
import AnalysisConfigPage from './pages/talent-intelligence/AnalysisConfigPage';
import TalentConfigurationPage from './pages/talent-intelligence/TalentConfigurationPage';
import ReferenceChecksPage from './pages/reference-checks/ReferenceChecksPage';
import HomePage from './pages/home/HomePage';
import NewHomePage from './pages/home/NewHomePage';
import AdoptionDashboardPage from './pages/adoption/AdoptionDashboardPage';
import ComponentShowcase from './pages/design-system/ComponentShowcase';
import PlatformAdoptionAccessPage from './pages/platform-admin/AdoptionAccessPage';
import AdoptionSettingsPage from './pages/admin/AdoptionSettingsPage';

// RAG Evaluations
import EvalsPage from './pages/evals/EvalsPage';
import TelemetryPage from './pages/ai-console/TelemetryPage';

// GEPA Optimizer
import GEPAOptimizerPage from './pages/gepa-optimizer/GEPAOptimizerPage';

// Prompt Management
import PromptManagementPage from './pages/prompt-management/PromptManagementPage';

// RAGFlow integrated into Data Analyst page

// Workspaces (RAGFlow Knowledge Bases)
import WorkspacesPage from './pages/domains/DomainsPage';
import WorkspaceDetailPage from './pages/domains/DomainDetailPage';
import DomainChatPage from './pages/chat/DomainChatPage';
import ChatPage from './pages/chat/ChatPage';

// Platform Admin Pages
import TenantManagementPage from './pages/platform-admin/TenantManagementPage';
import FeatureAllocationPage from './pages/platform-admin/FeatureAllocationPage';
import AdminManagementPage from './pages/platform-admin/AdminManagementPage';
import AIProvidersPage from './pages/platform-admin/AIProvidersPage';
import EmailIntegrationPage from './pages/platform-admin/EmailIntegrationPage';
import JobSchedulerPage from './pages/platform-admin/JobSchedulerPage';
import SsoPolicyPage from './pages/platform-admin/SsoPolicyPage';

// Tenant Admin Pages
import UsersRolesPage from './pages/tenant-admin/UsersRolesPage';
import ThemePage from './pages/tenant-admin/ThemePage';
import StorageSettingsPage from './pages/tenant-admin/StorageSettingsPage';
import SsoSettingsPage from './pages/tenant-admin/SsoSettingsPage';

// Building - Apps in active customer development
import ComingSoonPage from './pages/coming-soon/ComingSoonPage';

// Components
import LoadingSpinner from './components/common/LoadingSpinner';
import Layout from './components/layout/Layout';
import { ToastContainer, Card, CardContent, Button, ErrorBoundary } from './components/ui';
import { useToasts } from './stores/useToasts';
import { ShieldExclamationIcon } from '@heroicons/react/24/outline';
import { isAppletEnabled, isBaseChatPlatformEnabled, isFrontendPageEnabled } from './shared/lib/applets';

// Toast Wrapper - Connects Zustand store to DS ToastContainer
function ToastWrapper() {
  const toasts = useToasts(s => s.toasts);
  const dismiss = useToasts(s => s.dismiss);
  
  // Memoize the transformation to prevent infinite re-renders
  const dsToasts = React.useMemo(() => 
    toasts.map(toast => ({
      id: toast.id,
      variant: toast.kind as 'success' | 'error' | 'info' | 'warning' | 'default',
      message: toast.message,
      title: toast.title,
      duration: toast.duration ?? 6000,
      onDismiss: dismiss,
    })),
    [toasts, dismiss]
  );
  
  return <ToastContainer toasts={dsToasts} position="top-right" />;
}

// Protected Route Component
interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredPermissions?: string[];
  requireAll?: boolean;
}

function ProtectedRoute({ 
  children, 
  requiredPermissions = [], 
  requireAll = false 
}: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, hasAnyPermission, hasAllPermissions } = useAuth();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Check permissions if specified
  if (requiredPermissions.length > 0) {
    const hasPermission = requireAll
      ? hasAllPermissions(requiredPermissions)
      : hasAnyPermission(requiredPermissions);

    if (!hasPermission) {
      return (
        <div className="min-h-screen bg-gray-50 dark:bg-dark-bg flex items-center justify-center p-6">
          <Card className="max-w-md w-full">
            <CardContent className="p-8 text-center">
              <ShieldExclamationIcon className="w-16 h-16 text-red-500 mx-auto mb-4" />
              <h1 className="font-title text-2xl text-charcoal dark:text-gray-100 mb-4">
                Access Denied
              </h1>
              <p className="text-gray-500 dark:text-gray-400 mb-6">
                You don't have permission to access this page.
              </p>
              <Button onClick={() => window.history.back()}>
                Go Back
              </Button>
            </CardContent>
          </Card>
        </div>
      );
    }
  }

  return <>{children}</>;
}

// Public Route Component (redirects to dashboard if authenticated)
interface PublicRouteProps {
  children: React.ReactNode;
}

function PublicRoute({ children }: PublicRouteProps) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (isAuthenticated) {
    return <Navigate to="/home" replace />;
  }

  return <>{children}</>;
}

// App Routes Component
function AppRoutes() {
  const isRagEnabled = isBaseChatPlatformEnabled();
  const isAdoptionEnabled = isFrontendPageEnabled('adoption');
  const isTalentEnabled = isAppletEnabled('talent');
  const isSowEnabled = isFrontendPageEnabled('sow');
  const isContentWriterEnabled = isFrontendPageEnabled('content-research');
  const isDataConnectionsEnabled = isFrontendPageEnabled('data-connections');
  const isEvalsEnabled = isFrontendPageEnabled('evals');
  const isTelemetryEnabled = isFrontendPageEnabled('telemetry');
  const isGepaOptimizerEnabled = isFrontendPageEnabled('gepa-optimizer');
  const isPromptManagementEnabled = isFrontendPageEnabled('prompt-management');
  const isStorageSettingsEnabled = isFrontendPageEnabled('storage-settings');
  const isComingSoonEnabled = isFrontendPageEnabled('coming-soon');

  return (
    <Routes>
      {/* Public Routes */}
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />
      
      {/* Accept Invite - Public route for new users */}
      <Route
        path="/accept-invite"
        element={<AcceptInvitePage />}
      />

      {/* SSO callback route (token handoff from backend redirect) */}
      <Route
        path="/auth/sso/callback"
        element={<SSOCallbackPage />}
      />

      {/* Protected Routes */}

      {/* Home - User customizable dashboard */}
      <Route
        path="/home"
        element={
          <ProtectedRoute>
            <NewHomePage />
          </ProtectedRoute>
        }
      />

      {/* Old Home - Widget dashboard (legacy) */}
      <Route
        path="/home/widgets"
        element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        }
      />

      {/* Legacy redirects to Workspaces */}
      {isRagEnabled && (
        <>
          <Route path="/knowledge-base" element={<Navigate to="/workspaces" replace />} />
          <Route path="/domains" element={<Navigate to="/workspaces" replace />} />
          <Route path="/domains/:workspaceId" element={<Navigate to="/workspaces/:workspaceId" replace />} />
        </>
      )}

      {/* Workspaces (RAGFlow Knowledge Bases) */}
      {isRagEnabled && (
        <>
          <Route
            path="/workspaces"
            element={
              <ProtectedRoute requiredPermissions={['assistant:access', 'documents:write', 'platform:admin']} requireAll={false}>
                <WorkspacesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/workspaces/:workspaceId"
            element={
              <ProtectedRoute requiredPermissions={['assistant:access', 'documents:write', 'platform:admin']} requireAll={false}>
                <WorkspaceDetailPage />
              </ProtectedRoute>
            }
          />
        </>
      )}

      {isRagEnabled && (
        <Route
          path="/documents/library"
          element={
            <ProtectedRoute requiredPermissions={['assistant:documents:read', 'platform:admin']} requireAll={false}>
              <Layout>
                <DocumentLibrary />
              </Layout>
            </ProtectedRoute>
          }
        />
      )}

      {/* Search Routes */}
      <Route
        path="/search"
        element={
          <ProtectedRoute requiredPermissions={['assistant:access', 'platform:admin']} requireAll={false}>
            <div className="p-8 text-center">
              <h1 className="text-2xl font-bold text-text">Search</h1>
              <p className="text-muted mt-2">Document search coming soon...</p>
            </div>
          </ProtectedRoute>
        }
      />



      {/* Caylent Routes */}
      <Route
        path="/caylent/employees"
        element={
          <ProtectedRoute requiredPermissions={['assistant:access', 'platform:admin']} requireAll={false}>
            <EmployeesOverview />
          </ProtectedRoute>
        }
      />

      {/* Chat Routes (New) */}
      {isRagEnabled && (
        <>
          <Route
            path="/chat"
            element={
              <ProtectedRoute requiredPermissions={['assistant:access', 'platform:admin']} requireAll={false}>
                <ChatPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/chat/:workspaceId"
            element={
              <ProtectedRoute requiredPermissions={['assistant:access', 'platform:admin']} requireAll={false}>
                <ChatPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/chat/:workspaceId/:conversationId"
            element={
              <ProtectedRoute requiredPermissions={['assistant:access', 'platform:admin']} requireAll={false}>
                <ChatPage />
              </ProtectedRoute>
            }
          />
        </>
      )}
      {isSowEnabled && (
        <Route
          path="/sow"
          element={
            <ProtectedRoute requiredPermissions={['assistant:access', 'platform:admin']} requireAll={false}>
              <SowAutomationPage />
            </ProtectedRoute>
          }
        />
      )}
      {isContentWriterEnabled && (
        <Route
          path="/content-research"
          element={
            <ProtectedRoute requiredPermissions={['content_writer:read', 'content_writer:write', 'platform:admin']} requireAll={false}>
              <ContentResearchPage />
            </ProtectedRoute>
          }
        />
      )}

      {/* Legacy BI routes - redirect to new Chat */}
      {isRagEnabled && (
        <>
          <Route path="/data-analyst" element={<Navigate to="/chat" replace />} />
          <Route path="/data-analyst/insurance" element={<Navigate to="/chat" replace />} />
          <Route path="/data-analyst/fasb" element={<Navigate to="/chat" replace />} />
          <Route path="/business-intelligence" element={<Navigate to="/chat" replace />} />
        </>
      )}

      {/* Legacy Data Search routes - migrated to Chat */}
      {isRagEnabled && (
        <>
          <Route path="/data-search" element={<Navigate to="/chat" replace />} />
          <Route path="/data-search/:conversationId" element={<Navigate to="/chat" replace />} />
        </>
      )}

      {/* Data Connections Routes */}
      {isDataConnectionsEnabled && (
        <Route
          path="/data-connections"
          element={
            <ProtectedRoute requiredPermissions={['connections:read', 'platform:admin']} requireAll={false}>
              <Layout>
                <DataConnectionsPage />
              </Layout>
            </ProtectedRoute>
          }
        />
      )}

      {/* Talent Intelligence Routes */}
      {/* TalentIntelligencePage removed - functionality moved to Analysis Config */}
      {isTalentEnabled && <Route
        path="/talent/history"
        element={
          <ProtectedRoute requiredPermissions={['recruiter:history:read', 'platform:admin']} requireAll={false}>
            <Layout>
              <TalentAnalysisHistoryPage />
            </Layout>
          </ProtectedRoute>
        }
      />}
      {isTalentEnabled && <Route
        path="/talent/outreach"
        element={
          <ProtectedRoute requiredPermissions={['recruiter:results:read', 'platform:admin']} requireAll={false}>
            <Layout>
              <CandidateOutreachPage />
            </Layout>
          </ProtectedRoute>
        }
      />}
      {isTalentEnabled && <Route
        path="/talent/email-templates"
        element={
          <ProtectedRoute requiredPermissions={['recruiter:email_templates:read', 'platform:admin']} requireAll={false}>
            <Layout>
              <EmailTemplatesPage />
            </Layout>
          </ProtectedRoute>
        }
      />}
      {isTalentEnabled && <Route
        path="/talent/email-templates/new"
        element={
          <ProtectedRoute requiredPermissions={['recruiter:email_templates:read', 'platform:admin']} requireAll={false}>
            <Layout>
              <EmailTemplateEditorPage />
            </Layout>
          </ProtectedRoute>
        }
      />}
      {isTalentEnabled && <Route
        path="/talent/email-templates/:id"
        element={
          <ProtectedRoute requiredPermissions={['recruiter:email_templates:read', 'platform:admin']} requireAll={false}>
            <Layout>
              <EmailTemplateEditorPage />
            </Layout>
          </ProtectedRoute>
        }
      />}
      {isTalentEnabled && <Route
        path="/talent/analysis-config"
        element={
          <ProtectedRoute requiredPermissions={['recruiter:config:read', 'platform:admin']} requireAll={false}>
            <Layout>
              <AnalysisConfigPage />
            </Layout>
          </ProtectedRoute>
        }
      />}
      {isTalentEnabled && <Route
        path="/talent/configuration"
        element={
          <ProtectedRoute requiredPermissions={['recruiter:blueprints:read', 'platform:admin']} requireAll={false}>
            <Layout>
              <TalentConfigurationPage />
            </Layout>
          </ProtectedRoute>
        }
      />}

      {/* Reference Check Voice Agent */}
      {isTalentEnabled && <Route
        path="/reference-checks"
        element={
          <ProtectedRoute requiredPermissions={['recruiter:reference_checks:access', 'platform:admin']} requireAll={false}>
            <Layout>
              <ReferenceChecksPage />
            </Layout>
          </ProtectedRoute>
        }
      />}

      {/* Adoption Dashboard */}
      {isAdoptionEnabled && <Route
        path="/adoption"
        element={
          <ProtectedRoute requiredPermissions={['adoption:view_dashboard', 'platform:admin']} requireAll={false}>
            <AdoptionDashboardPage />
          </ProtectedRoute>
        }
      />}

      {/* Admin Routes - Integrated into main layout */}
      <Route
        path="/admin/documents"
        element={
          <ProtectedRoute requiredPermissions={['assistant:documents:read', 'platform:admin']} requireAll={false}>
            <Layout>
              <div className="p-8 text-center">
                <h1 className="text-2xl font-bold text-text">Document Management</h1>
                <p className="text-muted mt-2">Document management coming soon...</p>
              </div>
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/ai-models"
        element={
          <ProtectedRoute requiredPermissions={['admin:settings:providers:manage', 'platform:admin']} requireAll={false}>
            <Layout>
              <div className="p-8 text-center">
                <h1 className="text-2xl font-bold text-text">AI Models</h1>
                <p className="text-muted mt-2">AI model management coming soon...</p>
              </div>
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/analytics"
        element={
          <ProtectedRoute requiredPermissions={['audit:read', 'platform:admin']} requireAll={false}>
            <Layout>
              <div className="p-8 text-center">
                <h1 className="text-2xl font-bold text-text">Analytics</h1>
                <p className="text-muted mt-2">Analytics coming soon...</p>
              </div>
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/settings"
        element={
          <ProtectedRoute requiredPermissions={['admin:settings:read', 'platform:admin']} requireAll={false}>
            <AdminSettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/mcp-servers"
        element={
          <ProtectedRoute requiredPermissions={['admin:settings:read', 'platform:admin']} requireAll={false}>
            <Layout>
              <McpServersPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/adoption-settings"
        element={
          <ProtectedRoute requiredPermissions={['adoption:manage_sync', 'adoption:manage_sharing', 'platform:admin']} requireAll={false}>
            <AdoptionSettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/adoption-access"
        element={
          <Navigate to="/admin/adoption-settings" replace />
        }
      />
      <Route
        path="/admin/resume-parsing-test"
        element={
          <ProtectedRoute requiredPermissions={['platform:admin']}>
            <Layout>
              <ResumeParsingTestPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/agents"
        element={
          <ProtectedRoute requiredPermissions={['labs:agents:access', 'platform:admin']} requireAll={false}>
            <AgentConfigurationPage />
          </ProtectedRoute>
        }
      />

      {/* AI Console - RAG Evaluations, GEPA Optimizer, Prompt Management */}
      {/* These pages require ai_console:access OR platform:admin */}
      {isEvalsEnabled && <Route
        path="/evals"
        element={
          <ProtectedRoute requiredPermissions={['ai_console:access', 'platform:admin']}>
            <EvalsPage />
          </ProtectedRoute>
        }
      />}

      {isTelemetryEnabled && <Route
        path="/telemetry"
        element={
          <ProtectedRoute requiredPermissions={['ai_console:access', 'assistant:access', 'platform:admin']}>
            <TelemetryPage />
          </ProtectedRoute>
        }
      />}

      {isGepaOptimizerEnabled && <Route
        path="/gepa-optimizer"
        element={
          <ProtectedRoute requiredPermissions={['ai_console:access', 'platform:admin']}>
            <GEPAOptimizerPage />
          </ProtectedRoute>
        }
      />}

      {isPromptManagementEnabled && <Route
        path="/prompt-management"
        element={
          <ProtectedRoute requiredPermissions={['ai_console:access', 'platform:admin']}>
            <PromptManagementPage />
          </ProtectedRoute>
        }
      />}

      {isFrontendPageEnabled('tiny-model-studio') && <Route
        path="/ai-console/tiny-model-studio"
        element={
          <ProtectedRoute requiredPermissions={['ai_console:access', 'assistant:access', 'platform:admin']}>
            <TinyModelStudioPage />
          </ProtectedRoute>
        }
      />}

      {/* Platform Admin Routes (Eliza Super Admins) */}
      {/* All platform admin pages are now flat under /platform-admin/ */}
      <Route
        path="/platform-admin/admins"
        element={
          <ProtectedRoute requiredPermissions={['platform:admin']}>
            <Layout>
              <AdminManagementPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/platform-admin/providers"
        element={
          <ProtectedRoute requiredPermissions={['platform:admin']}>
            <Layout>
              <AIProvidersPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/platform-admin/email"
        element={
          <ProtectedRoute requiredPermissions={['platform:admin']}>
            <Layout>
              <EmailIntegrationPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/platform-admin/jobs"
        element={
          <ProtectedRoute requiredPermissions={['platform:admin']}>
            <Layout>
              <JobSchedulerPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/jobs"
        element={
          <ProtectedRoute requiredPermissions={['adoption:manage_jobs', 'platform:admin']} requireAll={false}>
            <Layout>
              <JobSchedulerPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/platform-admin/sso-policy"
        element={
          <ProtectedRoute requiredPermissions={['platform:admin']}>
            <Layout>
              <SsoPolicyPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/platform-admin/tenants"
        element={
          <ProtectedRoute requiredPermissions={['platform:admin']}>
            <Layout>
              <TenantManagementPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/platform-admin/features"
        element={
          <ProtectedRoute requiredPermissions={['platform:admin']}>
            <Layout>
              <FeatureAllocationPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/platform-admin/adoption"
        element={
          <ProtectedRoute requiredPermissions={['platform:admin']}>
            <Layout>
              <PlatformAdoptionAccessPage />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Legacy routes - redirect old paths to new flat structure */}
      <Route
        path="/platform-admin/settings"
        element={<Navigate to="/platform-admin/admins" replace />}
      />
      <Route
        path="/platform-admin/settings/providers"
        element={<Navigate to="/platform-admin/providers" replace />}
      />
      <Route
        path="/platform-admin/settings/email"
        element={<Navigate to="/platform-admin/email" replace />}
      />
      <Route
        path="/platform-admin/settings/jobs"
        element={<Navigate to="/platform-admin/jobs" replace />}
      />
      <Route
        path="/platform-admin/tenants/features"
        element={<Navigate to="/platform-admin/features" replace />}
      />
      <Route
        path="/platform-admin/tenants/adoption"
        element={<Navigate to="/platform-admin/adoption" replace />}
      />

      {/* Tenant Admin Routes (Customer Admins) */}
      <Route
        path="/tenant-admin/users"
        element={
          <ProtectedRoute requiredPermissions={['users:read', 'roles:read', 'platform:admin']} requireAll={false}>
            <Layout>
              <UsersRolesPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/tenant-admin/theme"
        element={
          <ProtectedRoute requiredPermissions={['theme:write', 'platform:admin']} requireAll={false}>
            <Layout>
              <ThemePage />
            </Layout>
          </ProtectedRoute>
        }
      />
      {isStorageSettingsEnabled && (
        <Route
          path="/tenant-admin/storage"
          element={
            <ProtectedRoute requiredPermissions={['workspaces:write', 'platform:admin']} requireAll={false}>
              <Layout>
                <StorageSettingsPage />
              </Layout>
            </ProtectedRoute>
          }
        />
      )}
      <Route
        path="/tenant-admin/storage"
        element={
          <ProtectedRoute requiredPermissions={['workspaces:write', 'platform:admin']} requireAll={false}>
            <Layout>
              <StorageSettingsPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/tenant-admin/sso"
        element={
          <ProtectedRoute requiredPermissions={['admin:settings:update', 'platform:admin']} requireAll={false}>
            <Layout>
              <SsoSettingsPage />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Profile Routes */}
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <div className="p-8 text-center">
              <h1 className="text-2xl font-bold text-text">Profile Settings</h1>
              <p className="text-muted mt-2">Profile settings coming soon...</p>
            </div>
          </ProtectedRoute>
        }
      />

      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <div className="p-8 text-center">
              <h1 className="text-2xl font-bold text-text">Settings</h1>
              <p className="text-muted mt-2">Settings coming soon...</p>
            </div>
          </ProtectedRoute>
        }
      />

      {/* Building - Apps in active customer development */}
      {isComingSoonEnabled && (
        <>
          <Route
            path="/deal-intelligence"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="deal-intelligence" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/rfp-responder"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="rfp-responder" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/customer-health"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="customer-health" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/ma-analyst"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="ma-analyst" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/spend-optimizer"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="spend-optimizer" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/regulatory-radar"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="regulatory-radar" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/onboarding-copilot"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="onboarding-copilot" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/competitive-intel"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="competitive-intel" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/campaign-optimizer"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="campaign-optimizer" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/contract-hub"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="contract-hub" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/it-service-desk"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="it-service-desk" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/supply-chain"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="supply-chain" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/product-insights"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="product-insights" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/eliza-engage"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="eliza-engage" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/incident-commander"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="incident-commander" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/partner-intelligence"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="partner-intelligence" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/board-report-generator"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="board-report-generator" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/knowledge-miner"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="knowledge-miner" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/brand-guardian"
            element={
              <ProtectedRoute requiredPermissions={['platform:admin']} requireAll={false}>
                <ComingSoonPage appId="brand-guardian" />
              </ProtectedRoute>
            }
          />
        </>
      )}

      {/* Design System - Component Showcase (public for development) */}
      <Route
        path="/design-system"
        element={<ComponentShowcase />}
      />

      {/* Default redirect */}
      <Route path="/" element={<Navigate to="/home" replace />} />

      {/* Legacy Domain Chat - URL: /:domainName/:conversationUuid */}
      {/* These catch-all routes handle legacy URLs and redirect to new structure */}
      {isRagEnabled && (
        <>
          <Route
            path="/:domainName/:conversationUuid"
            element={
              <ProtectedRoute requiredPermissions={['assistant:access', 'platform:admin']} requireAll={false}>
                <DomainChatPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/:domainName"
            element={
              <ProtectedRoute requiredPermissions={['assistant:access', 'platform:admin']} requireAll={false}>
                <DomainChatPage />
              </ProtectedRoute>
            }
          />
        </>
      )}
      
      {/* 404 Page */}
      <Route
        path="*"
        element={
          <div className="min-h-screen bg-gray-50 dark:bg-dark-bg flex items-center justify-center p-6">
            <Card className="max-w-md w-full">
              <CardContent className="p-8 text-center">
                <h1 className="font-title text-display text-charcoal dark:text-gray-100 mb-4">
                  404
                </h1>
                <p className="text-gray-500 dark:text-gray-400 mb-6">
                  The page you're looking for doesn't exist.
                </p>
                <Button onClick={() => window.history.back()}>
                  Go Back
                </Button>
              </CardContent>
            </Card>
          </div>
        }
      />
    </Routes>
  );
}

// Main App Component
function App() {
  const theme = useUI((s) => s.theme);
  const loadTheme = useTheme((s) => s.loadTheme);

  // Track OS preference when using system theme
  const [osPrefersDark, setOsPrefersDark] = React.useState<boolean | null>(null);
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = () => setOsPrefersDark(mq.matches);
    apply();
    mq.addEventListener?.('change', apply);
    return () => mq.removeEventListener?.('change', apply);
  }, []);

  // Load tenant theme on app initialization
  useEffect(() => {
    loadTheme();
  }, [loadTheme]);

  useEffect(() => {
    const root = document.documentElement;
    const resolved = theme === 'system'
      ? (osPrefersDark ? 'dark' : 'light')
      : theme;
    
    // Set data-theme attribute for CSS custom properties
    root.setAttribute('data-theme', resolved);
    
    // Add/remove 'dark' class for Tailwind dark mode
    if (resolved === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    
    const meta = document.querySelector("meta[name='theme-color']") as HTMLMetaElement | null;
    if (meta) {
      meta.content = resolved === 'dark' ? '#0F172A' : '#F9FAFB';  // DS slate-900 / gray-50
    }
  }, [theme, osPrefersDark]);

  return (
    <ErrorBoundary>
      <AuthProvider>
        <Router>
          <NavigationProvider>
            <div className="App">
              <AppRoutes />
              <ToastWrapper />
            </div>
          </NavigationProvider>
        </Router>
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
