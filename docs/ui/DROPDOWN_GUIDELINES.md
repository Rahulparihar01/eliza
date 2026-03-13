# Dropdown Styling Guidelines

**Last updated:** October 24, 2025  
**Audience:** Frontend engineers and designers building interactive menus

---

## Core Component

- Use `frontend/src/components/common/ReadableDropdown.tsx` for all menu-style dropdowns.  
- Import the shared styles from `frontend/src/components/common/ReadableDropdown.css`.  
- Pass menu options via the `ReadableDropdownOption` interface (`key`, `label`, `description`, `onClick`).

```tsx
import { ReadableDropdown, type ReadableDropdownOption } from '../../components/common/ReadableDropdown';
```

## Visual Requirements

| Aspect | Specification |
| --- | --- |
| Background | Fully opaque surface `#2B1420`; never use translucent overlays. |
| Items | Base `#381A27`, hover/active `#462134`, border highlight `#FF7B6B`. |
| Text | Labels `#F8F5F0`, descriptions `#E8D5C8` for readability. |
| Shadow | `0 24px 48px rgba(0, 0, 0, 0.7), 0 12px 24px rgba(0, 0, 0, 0.5)` per `ReadableDropdown.css`. |
| Radius | Menu `var(--radius-lg)`, items `var(--radius-md)`.

These values are centralized in `ReadableDropdown.css`; do not override inline.

## Layout & Positioning

- Render dropdowns inside a `relative` container to allow the menu to be absolutely positioned.  
- Apply the `readable-dropdown-menu` class which sets `z-index: 9999`; this keeps the menu above panes and cards.  
- If the host layout introduces additional stacking contexts (e.g., headers with low z-index), lift that container (see `DataConnectionsPage` header using `z-40`).

## Interaction Behaviors

- Use Headless UI’s `Menu` + `Transition` from `@headlessui/react` for accessibility and focus management.  
- Keep keyboard navigation intact by rendering options as `<Menu.Item>` with buttons.  
- Provide short descriptions for complex actions to aid scanability.

## Configuration Tips

- Width is optional; when set, supply a pixel string (`width="320px"`).  
- For contextual menus, pass `align="left" | "right"` to anchor edge alignment.  
- Disable the trigger via the `disabled` prop rather than removing it from the DOM (preserves layout).

## Checklist Before Shipping

- [ ] Uses `ReadableDropdown` component and shared CSS.  
- [ ] Menu remains readable against background (inspect at 100% zoom).  
- [ ] Menu layers above nearby cards and panes.  
- [ ] Hover and focus states match spec.  
- [ ] Screen reader announces labels and descriptions.  
- [ ] Interactions tested on both light/dark themes (if applicable).

---

**Reference Implementation:** `DataConnectionsPage` → `NewConnectionMenu` demonstrates the approved pattern.
