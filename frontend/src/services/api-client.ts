import Axios, { AxiosRequestConfig } from 'axios';

// Check REACT_APP_API_URL first, then fall back to NODE_ENV logic
// This allows docker-compose build args to override production defaults
const API_URL = process.env.REACT_APP_API_URL 
  || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001');

export const AXIOS_INSTANCE = Axios.create({
  baseURL: API_URL,
  timeout: 6000000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Flag to prevent infinite refresh loops
let isRefreshing = false;

// Public API endpoints that should not include auth tokens
const PUBLIC_API_ENDPOINTS = [
  '/v1/auth/invite/',
  '/v1/auth/login',
  '/v1/auth/refresh',
  '/v1/auth/sso/options',
];

// Request interceptor - add auth token and tenant context headers
AXIOS_INSTANCE.interceptors.request.use(
  (config) => {
    // Skip adding auth token for public endpoints
    const isPublicEndpoint = PUBLIC_API_ENDPOINTS.some(ep => config.url?.includes(ep));
    
    const token = localStorage.getItem('auth_token');
    if (token && !isPublicEndpoint) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // Add platform admin tenant viewing headers
    // These are set by the useAuth store when platform admin uses "View As" feature
    try {
      const authStorage = localStorage.getItem('auth-storage');
      if (authStorage) {
        const authState = JSON.parse(authStorage)?.state;
        
        // Check if viewing as a specific tenant
        if (authState?.viewingAsTenant?.tenantId) {
          config.headers['X-View-As-Tenant'] = authState.viewingAsTenant.tenantId;
        }
        
        // Check if cross-tenant access is enabled
        if (authState?.crossTenantAccess) {
          config.headers['X-Cross-Tenant-Access'] = 'true';
        }
      }
    } catch (e) {
      // Ignore parsing errors
    }
    
    return config;
  },
  (error) => Promise.reject(error)
);

// Public paths that should not trigger auth redirects
const PUBLIC_PATHS = [
  '/accept-invite',
  '/login',
  '/forgot-password',
  '/reset-password',
  '/auth/sso/callback',
];

// Check if current page is a public path that shouldn't redirect on auth errors
const isPublicPath = () => {
  return PUBLIC_PATHS.some(path => window.location.pathname.startsWith(path));
};

// Response interceptor - handle 401/403 errors (expired or invalid tokens)
AXIOS_INSTANCE.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status;
    const errorData = error.response?.data?.detail;
    
    // Skip auth error handling for public pages
    if (isPublicPath()) {
      return Promise.reject(error);
    }
    
    // Handle tenant deactivation (403 with specific error type)
    if (status === 403 && errorData?.error === 'tenant_deactivated') {
      // Store deactivation info for the banner
      localStorage.setItem('tenant_deactivated', JSON.stringify({
        tenantName: errorData.tenant_name,
        deactivatedAt: errorData.deactivated_at,
        message: errorData.message
      }));
      
      // Trigger a custom event that the app can listen for
      window.dispatchEvent(new CustomEvent('tenant-deactivated', { detail: errorData }));
      
      return Promise.reject(error);
    }
    
    // Handle 401 (Unauthorized) - try to refresh token
    if (status === 401 && !isRefreshing) {
      // If we're already on the login page, don't do anything
      if (window.location.pathname === '/login') {
        return Promise.reject(error);
      }
      
      isRefreshing = true;
      try {
        // Try to refresh token
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await AXIOS_INSTANCE.post('/v1/auth/refresh', {
            refresh_token: refreshToken,
          });
          
          const { access_token, refresh_token: newRefreshToken } = response.data;
          localStorage.setItem('auth_token', access_token);
          localStorage.setItem('refresh_token', newRefreshToken);
          
          // Retry original request
          isRefreshing = false;
          error.config.headers.Authorization = `Bearer ${access_token}`;
          return AXIOS_INSTANCE.request(error.config);
        } else {
          // No refresh token - clear auth and redirect to login
          // Keep isRefreshing true to prevent more redirect attempts
          localStorage.removeItem('auth_token');
          localStorage.removeItem('refresh_token');
          localStorage.removeItem('user');
          window.location.href = '/login?message=Your session has expired. Please log in again.';
          return Promise.reject(error);
        }
      } catch (refreshError) {
        // Refresh failed - logout
        // Keep isRefreshing true to prevent more redirect attempts
        localStorage.removeItem('auth_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        window.location.href = '/login?message=Your session has expired. Please log in again.';
        return Promise.reject(error);
      }
    }
    
    // Handle 403 (Forbidden) - token invalid or expired
    // This can happen with SSE endpoints or other auth failures
    if (status === 403 && error.response?.data?.message?.includes?.('Authentication failed')) {
      // If we're already on the login page, don't redirect
      if (window.location.pathname === '/login') {
        return Promise.reject(error);
      }
      
      // Clear auth and redirect to login
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
      window.location.href = '/login?message=Your session has expired. Please log in again.';
    }
    
    return Promise.reject(error);
  }
);

// Custom instance for Orval
export const customInstance = <T>(
  config: AxiosRequestConfig,
  options?: AxiosRequestConfig,
): Promise<T> => {
  const promise = AXIOS_INSTANCE.request<T>({
    ...config,
    ...options,
  }).then(({ data }) => data);

  return promise;
};

export default customInstance;

// Helper function to get API client for new endpoints
export const getCompaniesApi = () => AXIOS_INSTANCE;
export const getSettingsApi = () => AXIOS_INSTANCE;
