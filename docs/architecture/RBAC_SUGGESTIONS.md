# RBAC Specification - Improvement Suggestions

## Executive Summary

This document provides detailed suggestions for enhancing the Single-Tenant RBAC Specification based on enterprise security best practices and operational requirements. The current specification is well-structured and covers most needs, but these improvements would make it production-ready for high-security environments.

**Overall Assessment**: ✅ Excellent foundation covering 90% of enterprise RBAC needs
**Priority**: Implement high-priority suggestions for production deployment

---

## 🔧 High Priority Improvements

### 1. Role Hierarchy Refinement

**Issue**: Current roles don't follow true hierarchical inheritance
**Impact**: Permission management complexity and potential security gaps

**Suggested Implementation**:
```typescript
// True hierarchical inheritance
const roleHierarchy = {
  'viewer': ['documents:read', 'search:execute'],
  'analyst': [...viewer, 'documents:upload', 'documents:edit_own', 'search:advanced'],
  'manager': [...analyst, 'documents:edit_all', 'documents:delete', 'users:read'],
  'admin': [...manager, 'users:create', 'users:edit', 'models:configure'],
  'super_admin': [...admin, 'system:admin', 'users:delete']
};

// Helper function for inheritance
const expandRolePermissions = (role: string): string[] => {
  const hierarchy = ['viewer', 'analyst', 'manager', 'admin', 'super_admin'];
  const roleIndex = hierarchy.indexOf(role);
  
  return hierarchy
    .slice(0, roleIndex + 1)
    .flatMap(r => roleHierarchy[r]);
};
```

### 2. Resource-Level Permissions

**Issue**: No document ownership or team-based access controls
**Impact**: Users can access/modify documents they shouldn't

**Suggested Implementation**:
```typescript
// Enhanced permission structure
interface Permission {
  resource: string;
  action: string;
  scope?: 'own' | 'team' | 'department' | 'all';
  conditions?: {
    department?: string[];
    document_status?: string[];
    time_restrictions?: TimeWindow;
    ip_restrictions?: string[];
  };
}

// Permission examples
const enhancedPermissions = [
  'documents:edit_own',      // Can only edit own documents
  'documents:edit_team',     // Can edit team documents
  'documents:edit_all',      // Can edit all documents
  'documents:read_department', // Can read department documents
];

// Database schema addition
ALTER TABLE documents ADD COLUMN department VARCHAR(100);
ALTER TABLE documents ADD COLUMN team VARCHAR(100);
ALTER TABLE documents ADD COLUMN uploaded_by INTEGER REFERENCES users(id);
```

### 3. Audit Trail Implementation

**Issue**: Audit logging mentioned but not fully specified
**Impact**: No compliance tracking or security monitoring

**Suggested Database Schema**:
```sql
-- Comprehensive audit trail
CREATE TABLE user_audit_log (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  action VARCHAR(100) NOT NULL,
  resource_type VARCHAR(50),
  resource_id VARCHAR(100),
  old_values JSONB,
  new_values JSONB,
  ip_address INET,
  user_agent TEXT,
  session_id VARCHAR(255),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Permission change tracking
CREATE TABLE permission_changes (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  changed_by INTEGER REFERENCES users(id),
  old_role VARCHAR(50),
  new_role VARCHAR(50),
  old_permissions TEXT[],
  new_permissions TEXT[],
  reason TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Login attempt tracking
CREATE TABLE login_attempts (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255),
  ip_address INET,
  user_agent TEXT,
  success BOOLEAN,
  failure_reason VARCHAR(100),
  created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🔧 Medium Priority Improvements

### 4. Enhanced Security Features

**Password Policy & Account Security**:
```typescript
interface PasswordPolicy {
  minLength: number;
  requireUppercase: boolean;
  requireNumbers: boolean;
  requireSpecialChars: boolean;
  maxAge: number; // days
  preventReuse: number; // last N passwords
  complexityScore: number; // minimum entropy
}

interface SecuritySettings {
  maxFailedAttempts: number;
  lockoutDuration: number; // minutes
  requireMFA: string[]; // roles requiring MFA
  sessionTimeout: number; // minutes
  maxConcurrentSessions: number;
}

// Database additions
ALTER TABLE users ADD COLUMN password_changed_at TIMESTAMP;
ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN locked_until TIMESTAMP;
ALTER TABLE users ADD COLUMN mfa_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN mfa_secret VARCHAR(255);

CREATE TABLE password_history (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  password_hash VARCHAR(255),
  created_at TIMESTAMP DEFAULT NOW()
);
```

### 5. API User Role Enhancement

**Issue**: API User role too broad and lacks granularity
**Suggested Split**:
```typescript
const apiRoles = {
  'api_readonly': {
    permissions: ['documents:read', 'search:execute'],
    rateLimit: 1000, // requests per hour
    allowedEndpoints: ['/v1/documents', '/v1/search']
  },
  'api_standard': {
    permissions: ['documents:read', 'documents:upload', 'search:execute'],
    rateLimit: 5000,
    allowedEndpoints: ['/v1/documents', '/v1/search', '/v1/upload']
  },
  'api_admin': {
    permissions: ['documents:*', 'search:*', 'models:read'],
    rateLimit: 10000,
    allowedEndpoints: ['*']
  }
};

// API key scoping
CREATE TABLE api_keys (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  key_hash VARCHAR(255) UNIQUE,
  name VARCHAR(100),
  scoped_permissions TEXT[],
  rate_limit INTEGER,
  last_used_at TIMESTAMP,
  expires_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);
```

### 6. Temporary Role Assignments

**Use Case**: Temporary elevated access for specific projects
```sql
CREATE TABLE temporary_role_assignments (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  role_id INTEGER REFERENCES roles(id),
  granted_by INTEGER REFERENCES users(id),
  expires_at TIMESTAMP NOT NULL,
  reason TEXT NOT NULL,
  auto_revoke BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Scheduled job to revoke expired assignments
CREATE OR REPLACE FUNCTION revoke_expired_roles()
RETURNS void AS $$
BEGIN
  UPDATE user_roles 
  SET active = FALSE 
  WHERE id IN (
    SELECT ur.id 
    FROM user_roles ur
    JOIN temporary_role_assignments tra ON ur.user_id = tra.user_id 
    WHERE tra.expires_at < NOW() AND tra.auto_revoke = TRUE
  );
END;
$$ LANGUAGE plpgsql;
```

---

## 🔧 Low Priority Improvements

### 7. User Experience Enhancements

**Permission Request Workflow**:
```typescript
interface PermissionRequest {
  id: string;
  userId: string;
  requestedPermissions: string[];
  requestedRole?: string;
  justification: string;
  businessCase: string;
  approver?: string;
  status: 'pending' | 'approved' | 'denied' | 'expired';
  reviewedAt?: Date;
  reviewNotes?: string;
  expiresAt?: Date;
  createdAt: Date;
}

// React component for permission hints
const PermissionHint: React.FC<{ permission: string }> = ({ permission }) => {
  const requiredRole = getRequiredRole(permission);
  
  return (
    <Tooltip content={`Available with ${requiredRole} role`}>
      <Button 
        disabled 
        variant="ghost"
        onClick={() => requestPermission(permission)}
      >
        Request Access
      </Button>
    </Tooltip>
  );
};
```

### 8. Advanced Permission Features

**Context-Based Permissions**:
```typescript
interface ContextualPermission {
  permission: string;
  conditions: {
    timeWindow?: {
      start: string; // "09:00"
      end: string;   // "17:00"
      timezone: string;
      weekdays?: number[]; // 1-7
    };
    ipRestrictions?: string[]; // CIDR blocks
    deviceRestrictions?: string[]; // device fingerprints
    locationRestrictions?: string[]; // country codes
    documentStatus?: string[]; // draft, review, published
  };
}

// Usage example
const contextualPermissions = [
  {
    permission: 'documents:edit',
    conditions: {
      timeWindow: { start: '09:00', end: '17:00', timezone: 'UTC' },
      documentStatus: ['draft', 'review']
    }
  }
];
```

---

## 📋 Implementation Roadmap

### Phase 1: Security Foundations (Week 1-2)
- [ ] Implement audit trail database schema
- [ ] Add password policy enforcement
- [ ] Implement account lockout mechanism
- [ ] Add resource ownership checks

### Phase 2: Role Enhancement (Week 3-4)
- [ ] Implement hierarchical role inheritance
- [ ] Add temporary role assignments
- [ ] Enhance API user roles with scoping
- [ ] Add permission request workflow

### Phase 3: Advanced Features (Week 5-6)
- [ ] Implement contextual permissions
- [ ] Add MFA support for admin roles
- [ ] Create compliance reporting
- [ ] Add bulk user management

### Phase 4: User Experience (Week 7-8)
- [ ] Implement progressive disclosure
- [ ] Add role comparison views
- [ ] Create guided onboarding
- [ ] Add permission impact analysis

---

## 🎯 Quick Wins

These can be implemented immediately with minimal effort:

1. **Add audit logging**: Simple table creation and logging middleware
2. **Implement password policy**: Client-side validation + server enforcement
3. **Add resource ownership**: Single column addition to documents table
4. **Create permission request UI**: Simple form + approval workflow

---

## 📊 Success Metrics

- **Security**: Zero permission escalation incidents
- **Usability**: <5% permission-related support tickets
- **Compliance**: 100% audit trail coverage
- **Performance**: <100ms permission check latency

---

This roadmap provides a clear path to enhance the RBAC system while maintaining the excellent foundation already established.
