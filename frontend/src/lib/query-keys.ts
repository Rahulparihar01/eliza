// Build query keys hierarchically to avoid circular references
const healthBase = ['health'] as const;
const authBase = ['auth'] as const;
const documentsBase = ['documents'] as const;
const companyDataBase = ['company-data'] as const;
const modelsBase = ['models'] as const;
const configBase = ['config'] as const;
const adminBase = ['admin'] as const;
const adminUsersBase = [...adminBase, 'users'] as const;
const adminAuditBase = [...adminBase, 'audit'] as const;
const businessIntelligenceBase = ['business-intelligence'] as const;
const connectorsBase = ['connectors'] as const;

export const queryKeys = {
  // Health & System
  health: {
    all: healthBase,
    basic: () => [...healthBase, 'basic'] as const,
    detailed: () => [...healthBase, 'detailed'] as const,
  },

  // Authentication
  auth: {
    all: authBase,
    currentUser: () => [...authBase, 'current-user'] as const,
    sessions: () => [...authBase, 'sessions'] as const,
  },

  // Documents
  documents: {
    all: documentsBase,
    lists: () => [...documentsBase, 'list'] as const,
    list: (filters: {
      search?: string;
      status?: string;
      source?: string;
      sort?: string;
      order?: string;
      page?: number;
    }) => [...documentsBase, 'list', filters] as const,
    details: () => [...documentsBase, 'detail'] as const,
    detail: (id: number) => [...documentsBase, 'detail', id] as const,
    stats: (range: string) => [...documentsBase, 'stats', range] as const,
    recent: (limit?: number) => [...documentsBase, 'recent', limit ?? 5] as const,
  },

  // Company Data
  companyData: {
    all: companyDataBase,
    stats: (range: string) => [...companyDataBase, 'stats', range] as const,
    recentUploads: () => [...companyDataBase, 'recent-uploads'] as const,
  },

  // Models
  models: {
    all: modelsBase,
    list: () => [...modelsBase, 'list'] as const,
    providers: () => [...modelsBase, 'providers'] as const,
    provider: (name: string) => [...modelsBase, 'providers', name] as const,
    config: () => [...modelsBase, 'config'] as const,
  },

  // Configuration
  config: {
    all: configBase,
    full: () => [...configBase, 'full'] as const,
    branding: () => [...configBase, 'branding'] as const,
    dataSources: (enabledOnly?: boolean) => 
      [...configBase, 'data-sources', { enabledOnly }] as const,
    businessRules: () => [...configBase, 'business-rules'] as const,
  },

  // Admin
  admin: {
    all: adminBase,
    users: {
      all: adminUsersBase,
      lists: () => [...adminUsersBase, 'list'] as const,
      list: (filters: any) => [...adminUsersBase, 'list', filters] as const,
      detail: (id: string) => [...adminUsersBase, 'detail', id] as const,
    },
    audit: {
      all: adminAuditBase,
      logs: (filters: any) => [...adminAuditBase, 'logs', filters] as const,
      summary: () => [...adminAuditBase, 'summary'] as const,
    },
  },

  // Business Intelligence
  businessIntelligence: {
    questions: () => ['business-intelligence', 'questions'] as const,
    question: (questionId: string) => ['business-intelligence', 'question', questionId] as const,
    analysisResult: (questionId: string) => ['business-intelligence', 'analysis-result', questionId] as const,
    prompts: () => ['business-intelligence', 'prompts'] as const,
    telemetry: (questionId: string) => ['business-intelligence', 'telemetry', questionId] as const,
  },

  // Companies
  companies: {
    all: () => ['companies'] as const,
    accessible: () => ['companies', 'accessible'] as const,
  },

  // Settings
  settings: {
    all: () => ['settings'] as const,
    setting: (key: string) => ['settings', key] as const,
    defaultCompany: () => ['settings', 'default', 'company_hr_dataset'] as const,
  },

  // Connectors
  connectors: {
    all: connectorsBase,
    lists: () => [...connectorsBase, 'list'] as const,
    list: (filters?: { status?: string; type?: string }) => [...connectorsBase, 'list', filters] as const,
    details: () => [...connectorsBase, 'detail'] as const,
    detail: (id: string | number) => [...connectorsBase, 'detail', id] as const,
    health: (id: string | number) => [...connectorsBase, 'health', id] as const,
    syncHistory: (id: string | number, filters?: any) => [...connectorsBase, 'sync-history', id, filters] as const,
    statistics: (id: string | number) => [...connectorsBase, 'statistics', id] as const,
    telemetry: (id: number) => [...connectorsBase, 'telemetry', id] as const,
  },
} as const;

