# Navigation Customization Guide

## Overview

The navigation component (`frontend/src/components/layout/Navigation.tsx`) is **critical** for maintaining consistent UX across platform instances. This guide shows you exactly how to customize it for your customer's features.

## Navigation Structure

The navigation follows this structure:

```
┌─────────────────────────────────────┐
│  Navigation Header (when expanded)  │
│  - Welcome back                     │
│  - User avatar + name               │
│  - Role badge                       │
├─────────────────────────────────────┤
│  Navigation Content                 │
│                                     │
│  [Search Link] (optional)           │
│                                     │
│  INSIGHTS                           │
│  • My Insights                     │
│                                     │
│  DATA                               │
│  • Knowledge Base                  │
│  • [Your Data Sources]             │
│                                     │
│  [YOUR FEATURES SECTION]            │
│  • Feature 1                       │
│  • Feature 2                       │
│                                     │
│  BUSINESS INTELLIGENCE              │
│  • Business Intelligence           │
│                                     │
│  ADMINISTRATION                     │
│  • Admin Settings                  │
│  • Agent Configuration             │
├─────────────────────────────────────┤
│  Navigation Footer                  │
│  - Platform version                │
└─────────────────────────────────────┘
```

## Customization Steps

### Step 1: Update Navigation Configuration

Edit `frontend/src/components/layout/Navigation.tsx`:

```typescript
// Find the navigationConfig array (around line 48)
const navigationConfig: NavigationItem[] = [
  // Keep these standard sections:
  
  // Insights Section
  {
    label: 'My Insights',
    path: '/insights/my',
    icon: 'chart',
  },
  
  // Data Section
  {
    label: 'Knowledge Base',
    path: '/knowledge-base',
    icon: 'document',
    requiredPermissions: ['documents:read'],
  },
  
  // ADD YOUR FEATURES HERE:
  {
    label: 'Your Feature Name',
    path: '/your-feature',
    icon: 'briefcase', // Choose from available icons
    requiredPermissions: ['your-feature:read'], // Optional
  },
  
  // Business Intelligence (keep if using)
  {
    label: 'Business Intelligence',
    path: '/business-intelligence',
    icon: 'chat',
  },
  
  // Administration (keep)
  {
    label: 'Admin Settings',
    path: '/admin/settings',
    icon: 'settings',
    requiredPermissions: ['settings:read', 'system:admin'],
    requiresAny: true,
  },
];
```

### Step 2: Group Your Features into Sections

Update the section grouping logic (around line 320):

```typescript
export function Navigation({ collapsed = false, onToggle }: NavigationProps) {
  const { user } = useAuth();

  // Standard sections
  const insightsItems = navigationConfig.filter(item => item.path.startsWith('/insights'));
  const searchItem = navigationConfig.find(item => item.path === '/search');
  const dataItems = navigationConfig.filter(item =>
    ['knowledge-base'].includes(item.path.split('/')[1])
  );

  // ADD YOUR FEATURE SECTION:
  const yourFeatureItems = navigationConfig.filter(item =>
    item.path.startsWith('/your-feature') ||
    item.path.startsWith('/another-feature')
  );

  // Standard sections
  const biItems = navigationConfig.filter(item =>
    item.path.startsWith('/business-intelligence')
  );
  const adminItems = navigationConfig.filter(item =>
    item.path.startsWith('/admin')
  );

  return (
    <nav className={...}>
      {/* ... header ... */}
      
      <div className="flex-1 overflow-y-auto py-3 px-2">
        {/* Standard sections */}
        <NavSection title="INSIGHTS" collapsed={collapsed}>
          {insightsItems.map((item) => (
            <NavItem key={item.path} item={item} collapsed={collapsed} />
          ))}
        </NavSection>

        <NavSection title="DATA" collapsed={collapsed}>
          {dataItems.map((item) => (
            <NavItem key={item.path} item={item} collapsed={collapsed} />
          ))}
        </NavSection>

        {/* ADD YOUR FEATURE SECTION: */}
        {yourFeatureItems.length > 0 && (
          <NavSection title="YOUR FEATURES" collapsed={collapsed}>
            {yourFeatureItems.map((item) => (
              <NavItem key={item.path} item={item} collapsed={collapsed} />
            ))}
          </NavSection>
        )}

        {/* Standard sections */}
        <NavSection title="BUSINESS INTELLIGENCE" collapsed={collapsed}>
          {biItems.map((item) => (
            <NavItem key={item.path} item={item} collapsed={collapsed} />
          ))}
        </NavSection>

        <NavSection title="ADMINISTRATION" collapsed={collapsed}>
          {adminItems.map((item) => (
            <NavItem key={item.path} item={item} collapsed={collapsed} />
          ))}
        </NavSection>
      </div>
    </nav>
  );
}
```

### Step 3: Available Icons

Icons are from Heroicons. Available icon names:

```typescript
// Common icons (imported in Navigation.tsx):
'home'           // HomeIcon
'chart'          // ChartBarIcon
'document'       // DocumentTextIcon
'upload'         // CloudArrowUpIcon
'search'         // MagnifyingGlassIcon
'chip'           // CpuChipIcon
'users'          // UsersIcon
'calculator'     // CalculatorIcon
'settings'       // Cog6ToothIcon
'key'            // KeyIcon
'clipboard'      // ClipboardDocumentListIcon
'heart'          // HeartIcon
'briefcase'      // BriefcaseIcon
'chat'           // ChatBubbleLeftRightIcon
'link'           // LinkIcon
'sparkles'       // SparklesIcon
'envelope'        // EnvelopeIcon
'clock'           // ClockIcon (for history)
```

To add a new icon:

1. Import it at the top:
```typescript
import { YourIcon } from '@heroicons/react/24/outline';
```

2. Add to icon mapping:
```typescript
const iconMap = {
  // ... existing icons
  'your-icon': YourIcon,
};
```

### Step 4: Permissions

Navigation items can be protected with permissions:

```typescript
{
  label: 'Protected Feature',
  path: '/protected-feature',
  icon: 'briefcase',
  requiredPermissions: ['feature:read'], // User must have this permission
  requiresAny: false, // If true, user needs ANY permission. If false, needs ALL.
}
```

The `WithPermission` component automatically hides items the user can't access.

## Design Consistency

### Section Headers
- Always uppercase: `"YOUR SECTION NAME"`
- Use `NavSection` component
- Styled consistently across all sections

### Navigation Items
- Use consistent spacing
- Active state highlighting
- Icon + label alignment
- Hover states

### Collapsed State
- Only icons visible
- Tooltips on hover
- Maintains functionality

## Example: Adding a New Feature Section

```typescript
// 1. Add items to navigationConfig
{
  label: 'Claims Processing',
  path: '/claims',
  icon: 'document',
  requiredPermissions: ['claims:read'],
},
{
  label: 'Underwriting',
  path: '/underwriting',
  icon: 'calculator',
  requiredPermissions: ['underwriting:read'],
},
{
  label: 'Policy Management',
  path: '/policies',
  icon: 'briefcase',
  requiredPermissions: ['policies:read'],
},

// 2. Group them
const insuranceItems = navigationConfig.filter(item =>
  ['claims', 'underwriting', 'policies'].includes(item.path.split('/')[1])
);

// 3. Render section
{insuranceItems.length > 0 && (
  <NavSection title="INSURANCE" collapsed={collapsed}>
    {insuranceItems.map((item) => (
      <NavItem key={item.path} item={item} collapsed={collapsed} />
    ))}
  </NavSection>
)}
```

## Testing Navigation

After customizing:

1. **Start frontend**: `docker-compose up -d frontend`
2. **Check expanded state**: All sections visible, correct grouping
3. **Check collapsed state**: Icons visible, tooltips work
4. **Test permissions**: Login as different users, verify items show/hide correctly
5. **Test navigation**: Click items, verify routes work

## Common Mistakes

❌ **Don't**: Create custom navigation components outside the standard structure
✅ **Do**: Use `NavSection` and `NavItem` components

❌ **Don't**: Hardcode section titles in multiple places
✅ **Do**: Use the `navigationConfig` array as single source of truth

❌ **Don't**: Skip permission checks
✅ **Do**: Always add `requiredPermissions` for protected features

❌ **Don't**: Change navigation width or collapse behavior
✅ **Do**: Keep standard widths (`w-60` expanded, `w-16` collapsed)

## Maintenance

When adding new features:

1. Add to `navigationConfig` array
2. Update section grouping logic
3. Add route in `frontend/src/App.tsx`
4. Create page component
5. Test navigation behavior

---

**Remember**: The navigation is the primary UX element. Keep it consistent, organized, and permission-aware.

