# API Type Generation Specification

**Status**: Proposed  
**Last Updated**: 2025-09-29  
**Owner**: Engineering

## Overview

Automate TypeScript type and client generation from FastAPI's OpenAPI schema to ensure type safety and eliminate manual type maintenance.

## Current Problem

- Frontend TypeScript types (`frontend/src/types/api.ts`) are manually maintained
- No guarantee of sync between backend Pydantic models and frontend types
- Manual updates required for every API change
- Risk of runtime errors from type mismatches
- Duplication of effort defining types in two places

## Solution: Orval + OpenAPI

Use [Orval](https://orval.dev/) to automatically generate TypeScript types and React Query hooks from FastAPI's OpenAPI schema.

### Why Orval?

- **Types + Client Code**: Generates both TypeScript interfaces and API client functions
- **React Query Integration**: Auto-generates hooks (`useQuery`, `useMutation`) for each endpoint
- **Customizable**: Can override or extend generated code
- **Fast**: Incremental generation
- **Popular**: Well-maintained, 2.5k+ GitHub stars

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Backend (FastAPI + Pydantic)                               │
│  ├─ models/auth.py                                          │
│  ├─ models/document.py                                      │
│  └─ main.py                                                 │
│      └─ Serves OpenAPI schema at /openapi.json             │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ HTTP GET
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  OpenAPI Schema (JSON)                                      │
│  ├─ Paths (/v1/auth/login, /v1/documents, etc.)           │
│  ├─ Components/Schemas (User, Document, etc.)              │
│  └─ Request/Response types                                  │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ orval generate
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Generated TypeScript (frontend/src/generated/)            │
│  ├─ api.ts          - TypeScript types                     │
│  ├─ api.msw.ts      - Mock Service Worker handlers         │
│  └─ api.schemas.ts  - Zod schemas (optional)               │
└─────────────────────────────────────────────────────────────┘
```

## Implementation

### Step 1: Install Dependencies

```bash
cd frontend
npm install -D orval
npm install -D @tanstack/react-query  # already installed
```

### Step 2: Create Orval Configuration

Create `frontend/orval.config.ts`:

```typescript
import { defineConfig } from 'orval';

export default defineConfig({
  'ai-platform': {
    input: {
      target: 'http://localhost:5001/openapi.json',
    },
    output: {
      mode: 'tags-split',
      target: './src/generated/api.ts',
      schemas: './src/generated/models',
      client: 'react-query',
      mock: true,
      prettier: true,
      override: {
        mutator: {
          path: './src/services/api-client.ts',
          name: 'customInstance',
        },
      },
    },
    hooks: {
      afterAllFilesWrite: 'prettier --write',
    },
  },
});
```

### Step 3: Create Custom API Client Wrapper

Create `frontend/src/services/api-client.ts`:

```typescript
import Axios, { AxiosRequestConfig } from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

export const AXIOS_INSTANCE = Axios.create({
  baseURL: API_URL,
  timeout: 30000,
});

// Add auth token to requests
AXIOS_INSTANCE.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 errors
AXIOS_INSTANCE.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Handle token refresh or redirect to login
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const customInstance = <T>(
  config: AxiosRequestConfig
): Promise<T> => {
  return AXIOS_INSTANCE.request(config).then(({ data }) => data);
};

export default customInstance;
```

### Step 4: Update Package Scripts

Add to `frontend/package.json`:

```json
{
  "scripts": {
    "generate:api": "orval",
    "generate:api:watch": "orval --watch",
    "prebuild": "npm run generate:api",
    "predev": "npm run generate:api"
  }
}
```

### Step 5: Update .gitignore

Add to `frontend/.gitignore`:

```
# Generated API code
src/generated/
```

Or keep generated code in git for easier debugging (recommended):

```
# Do NOT ignore - keep generated code in git
# src/generated/
```

### Step 6: Update Backend OpenAPI Metadata

Ensure FastAPI exports comprehensive OpenAPI schema in `src/main.py`:

```python
app = FastAPI(
    title="AI Enablement Platform",
    description="Enterprise AI enablement and RAG platform",
    version="2.0.0",
    openapi_tags=[
        {"name": "auth", "description": "Authentication endpoints"},
        {"name": "documents", "description": "Document management"},
        {"name": "models", "description": "AI model configuration"},
        {"name": "health", "description": "Health checks"},
    ],
)
```

## Usage in Frontend

### Before (Manual Types)

```typescript
// Manual type definition
interface LoginRequest {
  email: string;
  password: string;
}

// Manual API call
const login = async (credentials: LoginRequest) => {
  const response = await apiService.request('POST', '/v1/auth/login', credentials);
  return response.data;
};

// Manual React Query hook
const { mutate: loginMutation } = useMutation({
  mutationFn: login,
  onSuccess: (data) => {
    // handle success
  },
});
```

### After (Generated)

```typescript
// Import generated types and hooks
import { useAuthLogin } from '@/generated/api';

// Use generated hook - types are automatic!
const { mutate: login, isPending } = useAuthLogin({
  mutation: {
    onSuccess: (data) => {
      // data is fully typed as LoginResponse
      console.log(data.user.email);
    },
  },
});

// Call with type-safe request
login({
  data: {
    email: 'user@example.com',
    password: 'password',
  },
});
```

## Developer Workflow

### Daily Development

1. **Start backend**: `docker-compose up`
2. **Generate types**: `npm run generate:api` (or runs automatically)
3. **Develop**: Types and hooks are ready to use
4. **Auto-watch mode**: `npm run generate:api:watch` for live regeneration

### When API Changes

1. Update Pydantic models in backend
2. Restart backend (Docker reload)
3. Run `npm run generate:api` in frontend
4. TypeScript compiler will show any breaking changes
5. Update frontend code to match new types
6. Commit both backend changes and generated types

## Migration Strategy

### Phase 1: Parallel Operation (Week 1)
- Set up Orval configuration
- Generate types alongside existing manual types
- Test generated types in non-critical components
- Compare generated vs manual types for accuracy

### Phase 2: Gradual Migration (Weeks 2-3)
- Migrate one module at a time (auth, documents, models)
- Update imports from manual types to generated types
- Test thoroughly in each module
- Keep manual types as fallback

### Phase 3: Complete Migration (Week 4)
- Remove `src/types/api.ts` manual types
- Update all imports to use generated code
- Remove old `apiService` wrapper
- Document new patterns for team

### Phase 4: Automation (Ongoing)
- Add type generation to CI/CD pipeline
- Fail builds if generated types don't match schema
- Auto-generate types on backend changes
- Keep generated code in version control

## Best Practices

### DO ✅
- Run type generation before every build
- Keep generated code in git for easier debugging
- Review generated code changes in PRs
- Use generated types everywhere
- Customize Orval config as needed
- Add JSDoc comments to backend models (appears in generated types)

### DON'T ❌
- Manually edit generated files (will be overwritten)
- Skip type generation step
- Mix manual and generated types for same endpoint
- Commit without regenerating after backend changes
- Override types unless absolutely necessary

## Troubleshooting

### Issue: "Cannot connect to OpenAPI endpoint"
**Solution**: Ensure backend is running on `localhost:5001`

### Issue: "Generated types don't match backend"
**Solution**: 
1. Check backend OpenAPI schema at `http://localhost:5001/openapi.json`
2. Restart backend to refresh schema
3. Clear Orval cache: `rm -rf frontend/node_modules/.orval`
4. Regenerate: `npm run generate:api`

### Issue: "TypeScript errors after generation"
**Solution**:
1. Check for breaking changes in backend
2. Update frontend code to match new types
3. If types are incorrect, fix backend Pydantic models
4. Regenerate types

### Issue: "Want to customize generated code"
**Solution**: Use Orval's override options in config:
- Custom client instance
- Custom hooks
- Zod schema generation
- MSW mock handlers

## Benefits

1. **Type Safety**: Compile-time checking of API contracts
2. **Auto-completion**: Full IntelliSense for all endpoints
3. **Refactoring**: Rename fields in backend → TypeScript errors show all places to update
4. **Documentation**: Generated types serve as living API documentation
5. **Faster Development**: No manual type definition
6. **Fewer Bugs**: Catch mismatches before runtime
7. **Consistency**: Single source of truth (backend models)

## Maintenance

- **Weekly**: Review generated code changes in PRs
- **Monthly**: Update Orval and dependencies
- **Quarterly**: Review and optimize Orval configuration
- **As Needed**: Customize generation for special cases

## References

- [Orval Documentation](https://orval.dev/)
- [FastAPI OpenAPI](https://fastapi.tiangolo.com/advanced/extending-openapi/)
- [React Query](https://tanstack.com/query/latest)
- [OpenAPI Specification](https://spec.openapis.org/oas/latest.html)

## Appendix: Example Generated Code

### Input (Backend Pydantic Model)

```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: Optional[bool] = False

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserProfile
```

### Output (Generated TypeScript)

```typescript
export interface LoginRequest {
  email: string;
  password: string;
  remember_me?: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: UserProfile;
}

export const useAuthLogin = (
  options?: UseMutationOptions<LoginResponse, Error, { data: LoginRequest }>
) => {
  return useMutation({
    mutationFn: (payload) => 
      customInstance<LoginResponse>({
        url: `/v1/auth/login`,
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        data: payload.data,
      }),
    ...options,
  });
};
```
