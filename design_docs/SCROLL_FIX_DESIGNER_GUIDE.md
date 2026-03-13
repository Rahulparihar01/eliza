# Scroll Fix - Designer Reference Guide

## Overview
Fixed the scrolling behavior so that individual panes scroll independently instead of the entire application scrolling. This creates better context retention and clearer boundaries between content regions.

## What Changed

### Before (Problem)
- ❌ Entire page scrolled when using mouse wheel
- ❌ Users lost context as content moved off screen
- ❌ No way to tell when reaching bottom of content
- ❌ Background gradient scrolled with content

### After (Fixed)
- ✅ Only individual content panes scroll
- ✅ Background stays fixed
- ✅ Each pane has independent scroll
- ✅ Overscroll bounce indicates boundaries
- ✅ Slim scrollbars appear on hover

## Scroll Regions (Element References)

### 1. Question List (Left Pane)
**Element Class**: `.questions-scroll-container`
**Location**: Business Intelligence Q&A → Left sidebar
**Behavior**:
- Vertical scroll only
- Slim scrollbar (4px) on hover
- Overscroll bounce on iOS/Safari
- Smooth momentum scrolling on touch devices
- **Always scrollable** (even with minimal content) for UX feedback

**Designer Notes**:
- Header "Recent Questions" stays fixed
- Only the list of questions scrolls
- Background gradient stays in place
- Question items use hover states independently
- List always has scrollability (15vh padding-bottom) - users can pull down from top or scroll past bottom to feel rubberband effect

### 2. Detail Pane (Center/Main Content)
**Element Class**: `.detail-scroll-container`  
**Location**: Business Intelligence Q&A → Center pane (question details)
**Behavior**:
- Vertical scroll only
- Slim scrollbar (4px) on hover
- Overscroll bounce on iOS/Safari
- **Always scrollable** (even with minimal content) for UX feedback
- Contains: status, original question, analysis result, timeline preview

**Designer Notes**:
- Fixed header with question title and status badge
- Detail sections scroll beneath header
- Each section (Processing Summary, Result, Timeline) is part of one continuous scroll
- No horizontal scroll
- Always has scrollability (15vh padding-bottom) with noticeable rubberband feedback when pulling down or scrolling past end

### 3. Timeline Pane (Right Pane - Optional)
**Element Class**: `.timeline-scroll-container`
**Location**: Business Intelligence Q&A → Far right (when open)
**Behavior**:
- Vertical scroll only
- Slim scrollbar (4px) on hover
- Overscroll bounce on iOS/Safari
- Shows agent execution timeline events

**Designer Notes**:
- Header "Agent Execution Timeline" with Close button stays fixed
- Timeline events scroll beneath header
- Can be toggled open/closed

## UX Rationale: Always-Scrollable Containers

### Why Force Scrollability?

Even when all content fits on screen, we ensure scroll containers remain slightly scrollable. This provides important UX benefits:

**1. Confirmation Feedback (Critical UX)**
- Users can "test" the scroll to confirm they're seeing everything
- **Even when all content is visible**, users can scroll and feel the rubberband
- Content visually moves and snaps back - immediate tactile feedback
- Scrolling and bouncing back signals "you've seen it all"
- Eliminates the question: "Is there more content below?"

**2. Consistent Interaction Model**
- All content panes behave the same way (always scrollable)
- Users don't need to wonder if scrolling is disabled or if they've reached the end
- Muscle memory works consistently across all states

**3. Visual Affordance**
- Slim scrollbar on hover indicates "this area is scrollable"
- Overscroll bounce reinforces boundaries
- Prevents "dead zone" feeling where scroll doesn't work

**4. Mobile/Touch Friendliness**
- Touch users expect scrollable areas to respond to swipes
- Small scroll distance + bounce = "you're at the end" signal
- Better than no feedback at all

### Implementation
```css
.overscroll-contain {
  overscroll-behavior-x: contain; /* Prevent horizontal scroll chaining */
  overscroll-behavior-y: auto;    /* Allow vertical bounce/rubberband */
}

.always-scrollable {
  padding-bottom: 15vh; /* ~15% of viewport height (~150px) */
  padding-top: 2px;     /* Enables pull-down bounce at top */
}
```

**Key Points:**
- `overflow-y: scroll` forces scrollability even when all content is visible
- `overscroll-behavior-y: auto` enables the native browser rubberband effect
- Enough padding (15vh) to ensure there's always scrollable space
- Users can pull down from top or scroll past bottom to feel the bounce
- Content visually moves and snaps back - tactile feedback
- Works on all browsers (Safari, Chrome, Firefox)

## Visual Specifications

### Scrollbar Design

```css
/* Scrollbar when hovered */
Width: 4px
Track: Transparent
Thumb: var(--border-strong) → rgba(43, 20, 32, 0.26)
Thumb Hover: var(--muted) → #8B3A52
Border Radius: Full (pill shape)

/* Scrollbar when not hovered */
Hidden (scrollbar-width: none)
```

### Overscroll Behavior

**What is Overscroll Bounce?**
When user scrolls past the top or bottom of content, there's a subtle "rubber band" bounce effect (native to iOS/Safari, simulated on other browsers).

**Purpose**:
- Provides tactile feedback that you've reached the end
- Prevents confusion about whether content is loading
- Creates more polished, app-like experience

**Visual Effect**:
- Content pulls slightly beyond boundary
- Springs back into place when released
- Does NOT trigger parent scroll

### Scroll Shadows (Optional Enhancement)

To further indicate scroll position, we can add subtle shadows:

**Top Shadow** (when scrolled down):
```css
Position: Sticky at top of scroll container
Height: 8px
Gradient: linear-gradient(
  to bottom,
  rgba(43, 20, 32, 0.12),
  transparent
)
```

**Bottom Shadow** (when more content below):
```css
Position: Sticky at bottom of scroll container
Height: 8px
Gradient: linear-gradient(
  to top,
  rgba(43, 20, 32, 0.12),
  transparent
)
```

## CSS Classes Applied

### On Scroll Containers
```css
.questions-scroll-container
.detail-scroll-container  
.timeline-scroll-container

/* With utilities */
.flex-1              /* Takes remaining space */
.min-h-0             /* Allows flex shrinking */
.overflow-y-scroll   /* Forces vertical scroll ALWAYS (even if content fits) */
.overscroll-contain  /* Allows vertical bounce, prevents horizontal chaining */
.scroll-slim         /* Slim hover-only scrollbar */
.ios-momentum        /* Smooth momentum on touch */
```

### On Global Elements
```css
html, body, #root {
  height: 100%;
  overflow: hidden;  /* Prevents document scroll */
}
```

## Device-Specific Behaviors

### Desktop (Mouse)
- Scrollbars hidden by default
- Appear on hover (4px slim)
- Mouse wheel scrolls active pane
- Shift + wheel for horizontal scroll (if needed)

### Laptop (Trackpad)
- Two-finger swipe to scroll
- Overscroll bounce on macOS
- Momentum scrolling
- Scrollbars fade in/out

### Tablet (Touch)
- One-finger swipe to scroll
- Overscroll bounce
- Momentum scrolling
- No scrollbars (touch interface)

### Mobile (Touch)
- One-finger swipe to scroll
- Strong overscroll bounce
- Fast momentum scrolling
- No scrollbars

## Testing Scenarios

### ✅ Should Work
1. Mouse wheel over question list → only list scrolls
2. Mouse wheel over detail pane → only detail scrolls
3. Dragging pane dividers → scroll containers adjust size
4. Resizing browser window → scroll containers adapt
5. Scrolling to bottom → bounce indicates end
6. Hover over scroll area → slim scrollbar appears

### ❌ Should NOT Happen
1. Mouse wheel scrolling causes entire page to scroll
2. Background gradient moves when scrolling
3. Scrolling in one pane causes other panes to scroll
4. Thick scrollbars taking up layout space
5. Horizontal scrollbars appearing

## Color Tokens Reference

For scroll-related UI elements:

```css
/* From design system */
--border-strong: rgba(43, 20, 32, 0.26)  /* Scrollbar thumb */
--muted: #8B3A52                          /* Scrollbar thumb hover */
--surface-2: rgba(255, 255, 255, 0.45)   /* Scroll track (hover only) */
--bg: #F8F5F0                             /* Background (stays fixed) */
--bg-gradient: linear-gradient(...)       /* Background gradient (fixed) */
```

## Implementation Files

For developer reference:
1. `frontend/src/index.css` - Global scroll styles
2. `frontend/src/components/layout/Layout.tsx` - Layout overflow handling
3. `frontend/src/pages/business-intelligence/BusinessIntelligenceQA.tsx` - Scroll containers
4. `design_docs/SCROLL_FIX_SPECIFICATION.md` - Technical specification

## Future Enhancements (Roadmap)

### Phase 2 (Optional)
- **Scroll Position Memory**: Remember position when navigating away
- **Smooth Scroll To**: Programmatic scrolling to specific items
- **Keyboard Navigation**: Page Up/Down, Home/End support

### Phase 3 (Performance)
- **Virtual Scrolling**: For lists with 1000+ items
- **Intersection Observers**: Lazy load timeline events

## Questions for Designer?

1. Should we add visual scroll shadows at top/bottom?
2. Should scrollbar thumb color change based on scroll depth?
3. Any preference for overscroll bounce distance?
4. Should we add scroll position indicators (e.g., "Scroll for more")?

