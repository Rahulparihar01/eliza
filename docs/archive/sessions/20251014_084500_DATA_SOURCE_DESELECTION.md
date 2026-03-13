# Data Source Selector - Toggle & Deselection
**Date**: October 14, 2025, 08:45 AM PST

## Overview
Added toggle behavior to the Data Source Selector, allowing users to deselect a connector by clicking it again or using the "Clear Selection" button.

## Changes Made

### 1. **Toggle Click Behavior** ✅
Updated `handleConnectorClick` to support deselection:

```typescript
const handleConnectorClick = (connectorId: string) => {
  if (selectedConnectorId === connectorId) {
    // Deselect if clicking the same connector
    onConnectorSelect(null);
  } else {
    // Select new connector
    onConnectorSelect(connectorId);
  }
};
```

### 2. **Updated Type Signature** ✅
Changed `onConnectorSelect` prop to accept `null`:

```typescript
interface DataSourceSelectorProps {
  selectedConnectorId: string | null;
  onConnectorSelect: (connectorId: string | null) => void;  // Now accepts null
  onContinue: (connectorId: string) => void;
  onBack: () => void;
}
```

### 3. **Clear Selection Button** ✅
Added explicit "Clear Selection" button in the footer:

```tsx
{selectedConnectorId && (
  <>
    <div className="flex items-center gap-2 text-sm text-muted-2">
      <CheckCircleIcon className="w-5 h-5 text-success" />
      <span>Data source selected</span>
    </div>
    <button
      onClick={() => onConnectorSelect(null)}
      className="px-4 py-2 text-sm text-muted-2 hover:text-text transition-colors"
    >
      Clear Selection
    </button>
  </>
)}
```

## User Experience

### Selection States
1. **No Selection**: All connectors shown in default state
2. **Selected**: Connector shows brand border, background, and checkmark
3. **Click Selected**: Returns to no selection state
4. **Click Different**: Switches selection to new connector

### Two Ways to Deselect
1. **Click the selected connector** - Toggles off
2. **Click "Clear Selection" button** - Explicit action

### Visual Feedback
- Selected connector: Brand color border and background
- Checkmark appears in selection indicator
- "Data source selected" message with green checkmark
- "Clear Selection" button appears when selected
- Hover states on all clickable elements

## Benefits

1. ✅ **User Control**: Can easily change or remove selection
2. ✅ **Intuitive**: Click to select, click again to deselect
3. ✅ **Clear Actions**: Explicit button for clarity
4. ✅ **Flexible Workflow**: Don't have to continue if you change your mind
5. ✅ **No Dead Ends**: Can always go back to zero state

## Testing Checklist

- [x] Click connector to select it
- [x] Click same connector again to deselect
- [x] Click "Clear Selection" button to deselect
- [x] Switch between different connectors
- [x] Deselect and verify "Continue" button is disabled
- [x] Visual states update correctly
- [x] No linter errors
- [x] Parent component handles null values correctly

## Files Modified

1. **`frontend/src/components/ml-talent/DataSourceSelector.tsx`**
   - Added `handleConnectorClick` with toggle logic
   - Updated `onConnectorSelect` type to accept `string | null`
   - Added "Clear Selection" button
   - Changed button click handler to use toggle function

2. **`frontend/src/pages/talent-intelligence/TalentIntelligencePage.tsx`**
   - Already handled `string | null` correctly in config state
   - No changes needed (type compatibility was already there)

## Summary

✅ **Toggle behavior implemented** - Click to select/deselect
✅ **Clear Selection button added** - Explicit deselection option
✅ **Type-safe implementation** - Handles null values correctly
✅ **Better UX** - Users can easily change their mind

The Data Source Selector now provides a more flexible and intuitive experience, allowing users to freely select, deselect, and change their data source choice!


