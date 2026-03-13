# Common Components

Reusable UI components for the Eliza Platform.

## SolidDropdown

A dropdown menu component with solid, opaque backgrounds that overrides the app's glass/transparent theme.

### Why This Component?

The Eliza Platform uses a "glass" design theme with semi-transparent backgrounds (defined in `src/index.css` as CSS variables like `--surface` and `--surface-2`). While this creates a beautiful aesthetic, it makes dropdown menus difficult to read when they overlay other content.

The `SolidDropdown` component solves this by:
- Using inline styles to ensure 100% opaque backgrounds
- Explicitly disabling backdrop filters
- Providing consistent, readable styling across all dropdowns

### Usage

```tsx
import { SolidDropdown } from '../../components/common/SolidDropdown';

// Simple example
<SolidDropdown
  trigger={<button>Open Menu</button>}
  options={[
    { 
      key: '1', 
      label: 'Option 1', 
      onClick: () => console.log('Clicked 1') 
    },
    { 
      key: '2', 
      label: 'Option 2', 
      description: 'With a description',
      onClick: () => console.log('Clicked 2') 
    }
  ]}
/>

// With all features
<SolidDropdown
  trigger={<button>Advanced Menu</button>}
  options={[
    { 
      key: 'available', 
      label: 'Available Option', 
      description: 'This option is clickable',
      available: true,
      onClick: () => handleClick() 
    },
    { 
      key: 'coming-soon', 
      label: 'Coming Soon', 
      description: 'This option is disabled',
      available: false,
      badge: 'Soon',
      onClick: () => {} 
    }
  ]}
  align="left"
  width="400px"
  disabled={isLoading}
/>
```

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `trigger` | `ReactNode` | required | The button/element that opens the dropdown |
| `options` | `DropdownOption[]` | required | Array of menu options |
| `align` | `'left' \| 'right'` | `'right'` | Alignment of dropdown relative to trigger |
| `width` | `string` | `'320px'` | Width of the dropdown menu |
| `disabled` | `boolean` | `false` | Disables the trigger button |

### DropdownOption Interface

```typescript
interface DropdownOption {
  key: string;           // Unique identifier
  label: string;         // Main text
  description?: string;  // Optional secondary text
  available?: boolean;   // If false, option is disabled (default: true)
  badge?: string;        // Optional badge text (e.g., "Soon", "New")
  onClick: () => void;   // Click handler
}
```

### Styling

The component uses inline styles for colors to ensure they override CSS variables:

- **Menu background**: `#111111` (very dark gray)
- **Option background**: `#1a1a1a` (dark gray)
- **Option hover**: `#2a2a2a` (lighter gray)
- **Border**: `#444444` (medium gray)
- **Active border**: `#FF9580` (brand color)
- **Text**: `white` for labels, `#888888` for descriptions
- **Badge**: `#222222` background, `#888888` text

### When to Use

Use `SolidDropdown` instead of raw Headless UI `Menu` components when:
- The dropdown will overlay other content
- Readability is critical
- You need consistent dropdown styling across the app

### Examples in Codebase

- **Data Connections Page**: New Connection menu (`src/pages/data-connections/DataConnectionsPage.tsx`)


