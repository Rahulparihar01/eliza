# Technical Specification
## Tenant Theme Settings

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | Draft |
| **Last Updated** | January 23, 2026 |
| **PRD Reference** | [01_PRODUCT_SPEC.md](./01_PRODUCT_SPEC.md) |
| **Author** | Development Agent |

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Data Model](#data-model)
4. [API Design](#api-design)
5. [Frontend Implementation](#frontend-implementation)
6. [Integration Points](#integration-points)
7. [Security Considerations](#security-considerations)
8. [Error Handling](#error-handling)
9. [Performance Considerations](#performance-considerations)
10. [Testing Strategy](#testing-strategy)
11. [Migration Strategy](#migration-strategy)
12. [Implementation Checklist](#implementation-checklist)

---

## Overview

This technical specification describes the implementation of tenant-scoped theme customization for Eliza Forge. The feature allows tenant administrators to customize brand colors (primary, primary-light, accent, text) which are then applied platform-wide for all users within that tenant.

### Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| New `tenant_themes` table | Cleaner separation from `customer_settings`, allows future extensibility (logos, dark mode variants) |
| New `theme:write` permission | Granular permission control separate from general admin settings |
| CSS custom properties for theming | Already used in the design system, allows runtime theme changes without CSS rebuilds |
| Zustand store for theme state | Consistent with existing state management patterns (e.g., `useUI` store) |
| Theme fetched on app init | Ensures theme is available before any UI renders |
| Cache theme in localStorage | Reduces API calls, provides instant theme on subsequent loads |

---

## Architecture

### System Context

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Frontend (React)                              │
│                                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐   │
│  │ ThemePage    │────▶│ useTheme     │────▶│ CSS Custom Properties │   │
│  │ (/tenant-    │     │ (Zustand)    │     │ (document.root)       │   │
│  │  admin/theme)│     └──────────────┘     └──────────────────────┘   │
│  └──────────────┘            │                                          │
│                              │ save/load                               │
│                              ▼                                          │
│                    ┌──────────────────┐                                │
│                    │ localStorage     │ (cache)                        │
│                    └──────────────────┘                                │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │ HTTP
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Backend (FastAPI)                               │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ /api/v1/tenant-settings/theme                                     │  │
│  │                                                                    │  │
│  │  GET  - Retrieve theme for current user's tenant                  │  │
│  │  PUT  - Update theme (requires admin:settings:write)              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ TenantTheme Model (SQLAlchemy)                                    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         PostgreSQL                                       │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ tenant_themes                                                       │ │
│  │   id | customer_id | primary_color | primary_light_color | ...     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Diagram

```
Frontend Components:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  ThemePage.tsx ─────────▶ ThemeCustomizer.tsx                          │
│       │                         │                                       │
│       │                         ├─▶ ColorPicker.tsx (x4)               │
│       │                         ├─▶ PresetButtons.tsx                  │
│       │                         └─▶ LivePreview.tsx                    │
│       │                                                                 │
│       └────────────────────────▶ useTheme.ts (Zustand store)           │
│                                         │                               │
│                                         └─▶ themeApi.ts (Orval)        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

Backend Components:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  routes/tenant_settings.py ──▶ schemas/tenant_settings.py              │
│           │                                                             │
│           └──────────────────▶ models/tenant_theme.py                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

**Load Theme Flow:**
1. User loads Eliza Forge app
2. `App.tsx` initializes, calls `useTheme().loadTheme()`
3. Store checks localStorage cache for theme
4. If cache miss or expired, fetches from `GET /api/v1/tenant-settings/theme`
5. Theme applied to CSS custom properties
6. Components render with theme colors

**Save Theme Flow:**
1. Tenant admin edits colors on Theme page
2. Live preview updates (local state only)
3. Admin clicks "Save Theme"
4. `PUT /api/v1/tenant-settings/theme` called
5. Backend validates & saves to database
6. Frontend updates Zustand store
7. CSS custom properties updated
8. localStorage cache updated
9. Success toast shown

---

## Data Model

### New Tables

```sql
-- alembic/versions/xxxx_add_tenant_themes.py

CREATE TABLE tenant_themes (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(100) NOT NULL UNIQUE,
    
    -- Color values (hex strings, validated format)
    primary_color VARCHAR(7) NOT NULL DEFAULT '#c9506b',
    primary_light_color VARCHAR(7) NOT NULL DEFAULT '#e8a598',
    accent_color VARCHAR(7) NOT NULL DEFAULT '#f5c4a1',
    text_color VARCHAR(7) NOT NULL DEFAULT '#5c4a5a',
    
    -- Preset tracking (null if custom colors)
    preset_name VARCHAR(50) DEFAULT 'eliza-forge',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Foreign key
    CONSTRAINT fk_tenant_themes_customer 
        FOREIGN KEY (customer_id) 
        REFERENCES customers(customer_id) 
        ON DELETE CASCADE
);

-- Indexes
CREATE UNIQUE INDEX idx_tenant_themes_customer ON tenant_themes(customer_id);
```

### SQLAlchemy Model

```python
# src/models/tenant_theme.py

from sqlalchemy import Column, String, ForeignKey
from src.models.database import BaseModel

class TenantTheme(BaseModel):
    """Tenant-specific theme/branding configuration."""
    
    __tablename__ = "tenant_themes"
    __table_args__ = ({'extend_existing': True},)
    
    # Multi-tenant - one theme per tenant
    customer_id = Column(
        String(100), 
        ForeignKey("customers.customer_id", ondelete="CASCADE"), 
        nullable=False, 
        unique=True, 
        index=True
    )
    
    # Brand colors (hex format: #RRGGBB)
    primary_color = Column(String(7), nullable=False, default='#c9506b')
    primary_light_color = Column(String(7), nullable=False, default='#e8a598')
    accent_color = Column(String(7), nullable=False, default='#f5c4a1')
    text_color = Column(String(7), nullable=False, default='#5c4a5a')
    
    # Preset name (null if custom colors)
    preset_name = Column(String(50), default='eliza-forge')
```

### Default Values

| Field | Default Value | Notes |
|-------|---------------|-------|
| `primary_color` | `#c9506b` | Eliza Forge red |
| `primary_light_color` | `#e8a598` | Light red |
| `accent_color` | `#f5c4a1` | Coral accent |
| `text_color` | `#5c4a5a` | Charcoal text |
| `preset_name` | `eliza-forge` | Default preset |

---

## API Design

### New Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/v1/tenant-settings/theme` | Get theme for current user's tenant | Authenticated |
| PUT | `/api/v1/tenant-settings/theme` | Update tenant theme | `theme:write` |

### Request/Response Models

```python
# src/api/schemas/tenant_settings.py

from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re

# Preset definitions (server-side validation)
THEME_PRESETS = {
    'eliza-forge': {
        'primary': '#c9506b',
        'primaryLight': '#e8a598',
        'accent': '#f5c4a1',
        'text': '#5c4a5a',
    },
    'ocean-blue': {
        'primary': '#0369a1',
        'primaryLight': '#38bdf8',
        'accent': '#06b6d4',
        'text': '#334155',
    },
    'forest-green': {
        'primary': '#15803d',
        'primaryLight': '#4ade80',
        'accent': '#84cc16',
        'text': '#374151',
    },
    'royal-purple': {
        'primary': '#7c3aed',
        'primaryLight': '#a78bfa',
        'accent': '#c084fc',
        'text': '#374151',
    },
}


class ThemeColors(BaseModel):
    """Color values for theme."""
    primary: str = Field(..., description="Primary brand color (hex)")
    primaryLight: str = Field(..., description="Light variant of primary (hex)")
    accent: str = Field(..., description="Accent/coral color (hex)")
    text: str = Field(..., description="Primary text color (hex)")
    
    @field_validator('primary', 'primaryLight', 'accent', 'text')
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        if not re.match(r'^#[0-9A-Fa-f]{6}$', v):
            raise ValueError(f'Invalid hex color format: {v}. Must be #RRGGBB')
        return v.lower()


class ThemeResponse(BaseModel):
    """Response containing theme data."""
    primary: str
    primaryLight: str
    accent: str
    text: str
    preset: Optional[str] = None
    
    class Config:
        from_attributes = True


class ThemeUpdateRequest(BaseModel):
    """Request to update theme."""
    primary: str = Field(..., description="Primary brand color (hex)")
    primaryLight: str = Field(..., description="Light variant of primary (hex)")
    accent: str = Field(..., description="Accent/coral color (hex)")
    text: str = Field(..., description="Primary text color (hex)")
    preset: Optional[str] = Field(None, description="Preset name if using preset")
    
    @field_validator('primary', 'primaryLight', 'accent', 'text')
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        if not re.match(r'^#[0-9A-Fa-f]{6}$', v):
            raise ValueError(f'Invalid hex color format: {v}. Must be #RRGGBB')
        return v.lower()
    
    @field_validator('preset')
    @classmethod
    def validate_preset(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in THEME_PRESETS:
            raise ValueError(f'Invalid preset: {v}. Valid presets: {list(THEME_PRESETS.keys())}')
        return v
```

### API Route Implementation

```python
# src/api/routes/tenant_settings.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.schemas.tenant_settings import ThemeResponse, ThemeUpdateRequest
from src.models.tenant_theme import TenantTheme
from src.middleware.authorization import require_permission
from src.core.database import get_db

router = APIRouter(prefix="/tenant-settings", tags=["Tenant Settings"])


@router.get("/theme", response_model=ThemeResponse)
async def get_tenant_theme(
    current_user=Depends(require_permission([])),  # Any authenticated user
    db: Session = Depends(get_db)
):
    """Get theme for current user's tenant."""
    theme = db.query(TenantTheme).filter(
        TenantTheme.customer_id == current_user.customer_id
    ).first()
    
    if not theme:
        # Return defaults if no theme configured
        return ThemeResponse(
            primary='#c9506b',
            primaryLight='#e8a598',
            accent='#f5c4a1',
            text='#5c4a5a',
            preset='eliza-forge'
        )
    
    return ThemeResponse(
        primary=theme.primary_color,
        primaryLight=theme.primary_light_color,
        accent=theme.accent_color,
        text=theme.text_color,
        preset=theme.preset_name
    )


@router.put("/theme", response_model=ThemeResponse)
async def update_tenant_theme(
    request: ThemeUpdateRequest,
    current_user=Depends(require_permission(["theme:write"])),
    db: Session = Depends(get_db)
):
    """Update theme for current user's tenant."""
    theme = db.query(TenantTheme).filter(
        TenantTheme.customer_id == current_user.customer_id
    ).first()
    
    if not theme:
        # Create new theme record
        theme = TenantTheme(
            customer_id=current_user.customer_id,
            primary_color=request.primary,
            primary_light_color=request.primaryLight,
            accent_color=request.accent,
            text_color=request.text,
            preset_name=request.preset
        )
        db.add(theme)
    else:
        # Update existing
        theme.primary_color = request.primary
        theme.primary_light_color = request.primaryLight
        theme.accent_color = request.accent
        theme.text_color = request.text
        theme.preset_name = request.preset
    
    db.commit()
    db.refresh(theme)
    
    return ThemeResponse(
        primary=theme.primary_color,
        primaryLight=theme.primary_light_color,
        accent=theme.accent_color,
        text=theme.text_color,
        preset=theme.preset_name
    )
```

### API Examples

```bash
# Get current theme
curl -X GET /api/v1/tenant-settings/theme \
  -H "Authorization: Bearer $TOKEN"

# Response
{
  "primary": "#c9506b",
  "primaryLight": "#e8a598",
  "accent": "#f5c4a1",
  "text": "#5c4a5a",
  "preset": "eliza-forge"
}

# Update theme with custom colors
curl -X PUT /api/v1/tenant-settings/theme \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "primary": "#0369a1",
    "primaryLight": "#38bdf8",
    "accent": "#06b6d4",
    "text": "#334155",
    "preset": "ocean-blue"
  }'
```

---

## Frontend Implementation

### Theme Store (Zustand)

```typescript
// frontend/src/stores/useTheme.ts

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ThemeColors {
  primary: string;
  primaryLight: string;
  accent: string;
  text: string;
}

interface ThemeState {
  colors: ThemeColors;
  preset: string | null;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setColors: (colors: ThemeColors, preset?: string | null) => void;
  loadTheme: () => Promise<void>;
  saveTheme: (colors: ThemeColors, preset?: string | null) => Promise<void>;
  resetToDefault: () => void;
  applyTheme: (colors: ThemeColors) => void;
}

const DEFAULT_THEME: ThemeColors = {
  primary: '#c9506b',
  primaryLight: '#e8a598',
  accent: '#f5c4a1',
  text: '#5c4a5a',
};

// Convert hex to RGB for CSS variables
function hexToRgb(hex: string): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return '201 80 107'; // fallback
  return `${parseInt(result[1], 16)} ${parseInt(result[2], 16)} ${parseInt(result[3], 16)}`;
}

export const useTheme = create<ThemeState>()(
  persist(
    (set, get) => ({
      colors: DEFAULT_THEME,
      preset: 'eliza-forge',
      isLoading: false,
      error: null,

      setColors: (colors, preset = null) => {
        set({ colors, preset });
        get().applyTheme(colors);
      },

      loadTheme: async () => {
        set({ isLoading: true, error: null });
        try {
          const response = await fetch('/api/v1/tenant-settings/theme', {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`,
            },
          });
          
          if (response.ok) {
            const data = await response.json();
            const colors = {
              primary: data.primary,
              primaryLight: data.primaryLight,
              accent: data.accent,
              text: data.text,
            };
            set({ colors, preset: data.preset, isLoading: false });
            get().applyTheme(colors);
          } else {
            // Use defaults on error
            set({ colors: DEFAULT_THEME, preset: 'eliza-forge', isLoading: false });
            get().applyTheme(DEFAULT_THEME);
          }
        } catch (error) {
          set({ error: 'Failed to load theme', isLoading: false });
          get().applyTheme(DEFAULT_THEME);
        }
      },

      saveTheme: async (colors, preset = null) => {
        set({ isLoading: true, error: null });
        try {
          const response = await fetch('/api/v1/tenant-settings/theme', {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${localStorage.getItem('token')}`,
            },
            body: JSON.stringify({
              primary: colors.primary,
              primaryLight: colors.primaryLight,
              accent: colors.accent,
              text: colors.text,
              preset,
            }),
          });
          
          if (response.ok) {
            set({ colors, preset, isLoading: false });
            get().applyTheme(colors);
          } else {
            throw new Error('Failed to save theme');
          }
        } catch (error) {
          set({ error: 'Failed to save theme', isLoading: false });
          throw error;
        }
      },

      resetToDefault: () => {
        set({ colors: DEFAULT_THEME, preset: 'eliza-forge' });
        get().applyTheme(DEFAULT_THEME);
      },

      applyTheme: (colors) => {
        document.documentElement.style.setProperty('--color-primary', hexToRgb(colors.primary));
        document.documentElement.style.setProperty('--color-primary-light', hexToRgb(colors.primaryLight));
        document.documentElement.style.setProperty('--color-accent', hexToRgb(colors.accent));
        document.documentElement.style.setProperty('--color-text', hexToRgb(colors.text));
      },
    }),
    {
      name: 'eliza-theme',
      partialize: (state) => ({ colors: state.colors, preset: state.preset }),
    }
  )
);
```

### Theme Page Component

```typescript
// frontend/src/pages/tenant-admin/ThemePage.tsx

import React, { useState, useEffect } from 'react';
import Layout from '../../components/layout/Layout';
import {
  Page,
  PageHeader,
  PageBody,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Button,
  Label,
  Input,
  Badge,
} from '../../components/ui';
import { SparklesIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import { useTheme } from '../../stores/useTheme';
import { useToast } from '../../hooks/useToast';

const PRESETS = {
  'eliza-forge': { primary: '#c9506b', primaryLight: '#e8a598', accent: '#f5c4a1', text: '#5c4a5a' },
  'ocean-blue': { primary: '#0369a1', primaryLight: '#38bdf8', accent: '#06b6d4', text: '#334155' },
  'forest-green': { primary: '#15803d', primaryLight: '#4ade80', accent: '#84cc16', text: '#374151' },
  'royal-purple': { primary: '#7c3aed', primaryLight: '#a78bfa', accent: '#c084fc', text: '#374151' },
};

export default function ThemePage() {
  const { colors: savedColors, preset: savedPreset, saveTheme, isLoading } = useTheme();
  const { addToast } = useToast();
  
  // Local state for editing
  const [localColors, setLocalColors] = useState(savedColors);
  const [localPreset, setLocalPreset] = useState(savedPreset);
  const [hasChanges, setHasChanges] = useState(false);
  
  useEffect(() => {
    setLocalColors(savedColors);
    setLocalPreset(savedPreset);
  }, [savedColors, savedPreset]);
  
  useEffect(() => {
    const changed = 
      localColors.primary !== savedColors.primary ||
      localColors.primaryLight !== savedColors.primaryLight ||
      localColors.accent !== savedColors.accent ||
      localColors.text !== savedColors.text;
    setHasChanges(changed);
  }, [localColors, savedColors]);
  
  const handleColorChange = (key: keyof typeof localColors, value: string) => {
    setLocalColors(prev => ({ ...prev, [key]: value }));
    setLocalPreset(null); // Mark as custom
  };
  
  const handlePresetSelect = (presetKey: string) => {
    const preset = PRESETS[presetKey as keyof typeof PRESETS];
    setLocalColors(preset);
    setLocalPreset(presetKey);
  };
  
  const handleSave = async () => {
    try {
      await saveTheme(localColors, localPreset);
      addToast({ type: 'success', message: 'Theme saved successfully!' });
    } catch (error) {
      addToast({ type: 'error', message: 'Failed to save theme' });
    }
  };
  
  const handleReset = () => {
    const defaultPreset = PRESETS['eliza-forge'];
    setLocalColors(defaultPreset);
    setLocalPreset('eliza-forge');
  };
  
  return (
    <Layout>
      <Page maxWidth="xl">
        <PageHeader
          title="Theme Settings"
          description="Customize your organization's color scheme"
          actions={
            <Button onClick={handleSave} disabled={!hasChanges || isLoading}>
              {isLoading ? 'Saving...' : 'Save Theme'}
            </Button>
          }
        />
        <PageBody>
          <Card>
            <div className="h-1 bg-gradient-to-r from-eliza-red via-eliza-red-light to-eliza-red-coral" />
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <SparklesIcon className="h-5 w-5 text-eliza-red" />
                Theme Customizer
              </CardTitle>
              <CardDescription>
                Adjust brand colors - all components update automatically
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-8">
                {/* Color Pickers */}
                <div className="space-y-4">
                  <h4 className="text-sm font-medium text-charcoal dark:text-white">Brand Colors</h4>
                  
                  <div className="grid grid-cols-2 gap-4">
                    {(['primary', 'primaryLight', 'accent', 'text'] as const).map((colorKey) => (
                      <div key={colorKey} className="space-y-2">
                        <Label htmlFor={colorKey}>
                          {colorKey === 'primaryLight' ? 'Primary Light' : 
                           colorKey.charAt(0).toUpperCase() + colorKey.slice(1)}
                        </Label>
                        <div className="flex items-center gap-2">
                          <input
                            type="color"
                            id={colorKey}
                            value={localColors[colorKey]}
                            onChange={(e) => handleColorChange(colorKey, e.target.value)}
                            className="w-10 h-10 rounded-lg border border-gray-200 dark:border-dark-border cursor-pointer"
                          />
                          <Input
                            value={localColors[colorKey]}
                            onChange={(e) => handleColorChange(colorKey, e.target.value)}
                            className="font-mono text-sm"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Presets */}
                <div className="space-y-4">
                  <h4 className="text-sm font-medium text-charcoal dark:text-white">Brand Presets</h4>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(PRESETS).map(([name, colors]) => (
                      <button
                        key={name}
                        onClick={() => handlePresetSelect(name)}
                        className={`
                          flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium
                          border transition-all
                          ${localPreset === name
                            ? 'border-eliza-red bg-eliza-red/10 text-eliza-red'
                            : 'border-gray-200 dark:border-dark-border hover:border-gray-300'
                          }
                        `}
                      >
                        <div
                          className="w-4 h-4 rounded-full"
                          style={{ backgroundColor: colors.primary }}
                        />
                        {name.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                      </button>
                    ))}
                  </div>
                  
                  <div className="pt-4">
                    <Button variant="outline" size="sm" onClick={handleReset}>
                      <ArrowPathIcon className="h-4 w-4 mr-2" />
                      Reset to Default
                    </Button>
                  </div>
                </div>
              </div>

              {/* Live Preview */}
              <div className="mt-6 p-4 rounded-xl bg-gray-50 dark:bg-dark-surface-2">
                <div className="flex items-center gap-4 flex-wrap">
                  <span className="text-sm text-gray-500 dark:text-gray-400">Live Preview:</span>
                  <Button 
                    variant="brand" 
                    size="sm"
                    style={{ backgroundColor: localColors.primary }}
                  >
                    Primary Button
                  </Button>
                  <Button variant="secondary" size="sm">Secondary</Button>
                  <Badge 
                    variant="brand"
                    style={{ backgroundColor: `${localColors.primary}20`, color: localColors.primary }}
                  >
                    Brand Badge
                  </Badge>
                  <span style={{ color: localColors.primary }} className="font-medium">
                    Accent Text
                  </span>
                  <div 
                    className="h-6 w-24 rounded-full"
                    style={{ 
                      background: `linear-gradient(to right, ${localColors.primary}, ${localColors.primaryLight}, ${localColors.accent})`
                    }}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </PageBody>
      </Page>
    </Layout>
  );
}
```

### Navigation Updates

```typescript
// frontend/src/components/navigation/sectionConfigs.ts

// Add import
import { SwatchIcon } from '@heroicons/react/24/outline';

// Update adminSettingsConfig
export const adminSettingsConfig: SectionConfig = {
  id: 'admin-settings',
  title: 'Admin Settings',
  icon: Cog6ToothIcon,
  basePath: '/admin',
  items: [
    { label: 'Data Connections', path: '/data-connections', icon: LinkIcon },
    { label: 'Users & Roles', path: '/tenant-admin/users', icon: UsersIcon },
    { label: 'AI Providers', path: '/admin/settings', icon: CpuChipIcon },
    { label: 'Theme', path: '/tenant-admin/theme', icon: SwatchIcon },  // NEW
  ],
};

// Update getSectionFromPath
export function getSectionFromPath(path: string): ActiveSection {
  // ... existing code ...
  
  // Admin settings paths - add theme path
  if (path.startsWith('/data-connections') || 
      path.startsWith('/tenant-admin/users') || 
      path.startsWith('/tenant-admin/theme') ||  // ADD THIS
      path.startsWith('/admin/settings')) {
    return 'admin-settings';
  }
  
  return null;
}
```

### App.tsx Route Addition

```typescript
// In App.tsx, add route:

import ThemePage from './pages/tenant-admin/ThemePage';

// In AppRoutes:
<Route
  path="/tenant-admin/theme"
  element={
    <ProtectedRoute requiredPermissions={['theme:write', 'platform:admin']} requireAll={false}>
      <ThemePage />
    </ProtectedRoute>
  }
/>
```

### Theme Loading in App

```typescript
// In App.tsx, add theme loading:

import { useTheme } from './stores/useTheme';

function App() {
  const loadTheme = useTheme((s) => s.loadTheme);
  
  useEffect(() => {
    // Load theme on app init (after auth context is ready)
    loadTheme();
  }, [loadTheme]);
  
  // ... rest of App
}
```

---

## Integration Points

### Existing Services

| Service | Usage | Location |
|---------|-------|----------|
| Authorization middleware | Permission checking | `src/middleware/authorization.py` |
| Database session | DB access | `src/core/database.py` |
| Customer model | Multi-tenant FK | `src/models/customer.py` |

### Existing Frontend

| Component | Usage | Location |
|-----------|-------|----------|
| Design System CSS Variables | Theme targets | `frontend/tailwind.config.js` |
| useUI store | Theme mode (dark/light) | `frontend/src/stores/useUI.ts` |
| AuthContext | Current user/tenant | `frontend/src/contexts/AuthContext.tsx` |

---

## Security Considerations

### Authentication & Authorization

- **Read theme:** Any authenticated user can read their tenant's theme
- **Write theme:** Requires `theme:write` permission
- **Multi-tenant:** All queries filter by `customer_id` from JWT

### Data Validation

| Input | Validation |
|-------|------------|
| Hex colors | Regex: `^#[0-9A-Fa-f]{6}$` |
| Preset name | Enum validation against allowed presets |

### Injection Prevention

- Hex colors validated before storage
- No arbitrary CSS allowed
- Values applied via CSS custom properties only

---

## Error Handling

| Error Case | HTTP Code | Response | Handling |
|------------|-----------|----------|----------|
| Invalid hex color | 422 | Pydantic validation error | Show form error |
| Invalid preset | 422 | Pydantic validation error | Show form error |
| Unauthorized | 401 | `{"detail": "Not authenticated"}` | Redirect to login |
| Forbidden | 403 | `{"detail": "Permission denied"}` | Show access denied |
| Database error | 500 | `{"detail": "Internal error"}` | Show error toast |

---

## Performance Considerations

### Caching Strategy

- Theme cached in localStorage via Zustand persist middleware
- Cache key: `eliza-theme`
- On save: Cache automatically updated
- On load: Check cache first, then API fallback

### Query Optimization

- Single-row lookup by unique index `customer_id`
- No pagination needed (single record per tenant)

---

## Testing Strategy

### Unit Tests

```python
# tests/test_tenant_theme.py

def test_get_theme_returns_defaults_when_none_exists():
    """New tenant should get default Eliza Forge theme."""
    
def test_get_theme_returns_saved_values():
    """Tenant with saved theme should get their values."""
    
def test_update_theme_validates_hex_format():
    """Invalid hex colors should be rejected."""
    
def test_update_theme_requires_permission():
    """Users without theme:write should get 403."""
    
def test_update_theme_multi_tenant_isolation():
    """Tenant A cannot update tenant B's theme."""
```

### Integration Tests

- [ ] API endpoint returns correct response
- [ ] Database records created correctly
- [ ] Multi-tenant isolation verified
- [ ] Permissions enforced

### E2E Tests

- [ ] Admin can load theme page
- [ ] Color pickers update preview
- [ ] Preset selection works
- [ ] Save persists to database
- [ ] Theme loads on app refresh

---

## Migration Strategy

### Database Migration

```python
# alembic/versions/xxxx_add_tenant_themes.py

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'tenant_themes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('primary_color', sa.String(7), nullable=False, server_default='#c9506b'),
        sa.Column('primary_light_color', sa.String(7), nullable=False, server_default='#e8a598'),
        sa.Column('accent_color', sa.String(7), nullable=False, server_default='#f5c4a1'),
        sa.Column('text_color', sa.String(7), nullable=False, server_default='#5c4a5a'),
        sa.Column('preset_name', sa.String(50), server_default='eliza-forge'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('customer_id')
    )
    op.create_index('idx_tenant_themes_customer', 'tenant_themes', ['customer_id'])

def downgrade():
    op.drop_index('idx_tenant_themes_customer')
    op.drop_table('tenant_themes')
```

### Deployment Order

1. Run database migration
2. Deploy backend changes (new route, model)
3. Deploy frontend changes (page, store, route)
4. Verify health checks

### Rollback Plan

1. Revert frontend deployment
2. Revert backend deployment
3. Run `alembic downgrade -1`

---

## Implementation Checklist

### Backend

- [ ] Create `src/models/tenant_theme.py` with SQLAlchemy model
- [ ] Create `src/api/schemas/tenant_settings.py` with Pydantic models
- [ ] Create `src/api/routes/tenant_settings.py` with GET/PUT endpoints
- [ ] Register router in `src/main.py`
- [ ] Create alembic migration
- [ ] Add tests

### Frontend

- [ ] Create `frontend/src/stores/useTheme.ts` Zustand store
- [ ] Create `frontend/src/pages/tenant-admin/ThemePage.tsx`
- [ ] Update `sectionConfigs.ts` with Theme nav item
- [ ] Update `getSectionFromPath` to include theme path
- [ ] Add route in `App.tsx`
- [ ] Add theme loading to `App.tsx` useEffect
- [ ] Add toast notifications for save success/error

### Testing

- [ ] Backend unit tests
- [ ] Frontend component tests
- [ ] E2E flow test

### Documentation

- [ ] Update API docs
- [ ] Update DESIGN_SYSTEM_GUIDE.md with theming info
