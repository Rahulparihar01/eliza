# Scroll Containment Fix Specification

## Problem Statement
The Business Intelligence Q&A page allows the entire application to scroll rather than having independent scroll regions for the question list and detail pane. This creates a poor UX where users lose context and can't tell when they've reached the bottom of content.

## Design Requirements

### 1. No Application-Level Scroll
- The entire application wrapper should NOT scroll
- Only specific content regions should be scrollable
- Background gradient should remain fixed

### 2. Independent Scroll Regions
Three separate scrollable areas:

#### A. **Question List** (Left Pane)
- **Element ID**: `.questions-scroll-container`
- **Behavior**: Vertical scroll only, slim scrollbar on hover
- **Bounce**: Subtle overscroll bounce on iOS/Safari
- **Height**: Fills available space between header and bottom

#### B. **Detail Pane** (Center/Right)
- **Element ID**: `.detail-scroll-container`
- **Behavior**: Vertical scroll only, slim scrollbar on hover  
- **Bounce**: Subtle overscroll bounce on iOS/Safari
- **Height**: Fills available space between fixed header and bottom

#### C. **Timeline Pane** (Far Right - Optional)
- **Element ID**: `.timeline-scroll-container`
- **Behavior**: Vertical scroll only, slim scrollbar on hover
- **Bounce**: Subtle overscroll bounce on iOS/Safari
- **Height**: Fills available space between header and bottom

### 3. Scroll Bounce Animation
Visual feedback when user reaches top/bottom of scrollable content:

```css
/* Overscroll behavior for modern browsers */
.scroll-bounce {
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
}

/* Visual indicator at scroll boundaries */
.scroll-boundary-indicator {
  position: sticky;
  top: 0;
  height: 2px;
  background: linear-gradient(
    to bottom,
    var(--border-strong),
    transparent
  );
  opacity: 0;
  transition: opacity 0.2s ease-out;
}

.scroll-boundary-indicator.visible {
  opacity: 1;
}
```

## Technical Implementation

### Step 1: Fix Body/HTML Overflow

```css
/* index.css */
html, body, #root {
  height: 100%;
  overflow: hidden; /* Prevent document scroll */
  margin: 0;
  padding: 0;
}
```

### Step 2: Update Layout Component

```tsx
// Layout.tsx - Line 40
<div className="h-screen flex flex-col bg-bg overflow-hidden">
  
  // Line 104 - Page Content wrapper
  <div className="flex-1 overflow-hidden min-h-0">
    <div className={`h-full ${showRightPanel ? 'flex' : ''} overflow-hidden`}>
      // Content...
    </div>
  </div>
</div>
```

### Step 3: Update BusinessIntelligenceQA.tsx

```tsx
// Line 314 - Main container (already correct)
<div className="h-full flex flex-col px-0 py-1 overflow-hidden">

// Line 358 - Question List Scroll Container
<div className="questions-scroll-container flex-1 min-h-0 overflow-y-auto overscroll-contain scroll-slim ios-momentum">
  // Question list items...
</div>

// Line 536 - Detail Pane Scroll Container  
<div className="detail-scroll-container flex-1 min-h-0 overflow-y-auto overscroll-contain scroll-slim ios-momentum">
  // Detail content...
</div>

// Line 445 - Timeline Scroll Container (already has correct classes)
<div className="timeline-scroll-container flex-1 min-h-0 p-4 overflow-y-auto overscroll-contain scroll-slim ios-momentum">
  // Timeline content...
</div>
```

### Step 4: Add Scroll Boundary Indicators (Optional Enhancement)

```tsx
// Add to each scroll container
function ScrollContainer({ children, className }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showTopShadow, setShowTopShadow] = useState(false);
  const [showBottomShadow, setShowBottomShadow] = useState(false);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = element;
      setShowTopShadow(scrollTop > 10);
      setShowBottomShadow(scrollTop < scrollHeight - clientHeight - 10);
    };

    element.addEventListener('scroll', handleScroll);
    handleScroll(); // Initial check
    
    return () => element.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div ref={scrollRef} className={className}>
      {showTopShadow && (
        <div className="scroll-boundary-indicator top" />
      )}
      {children}
      {showBottomShadow && (
        <div className="scroll-boundary-indicator bottom" />
      )}
    </div>
  );
}
```

## CSS Classes Reference (for Designer)

### Scroll Container Classes
```css
/* Applied to scrollable regions */
.questions-scroll-container { }
.detail-scroll-container { }
.timeline-scroll-container { }

/* Existing utility classes */
.scroll-slim          /* Slim scrollbar, hover to show */
.ios-momentum         /* Smooth momentum scrolling on iOS */
.overscroll-contain   /* Prevents scroll chaining to parent */
.min-h-0              /* Allows flex shrinking */
.overflow-y-auto      /* Enables vertical scroll */
```

### Scroll States
```css
/* When scrolled from top */
.scrolled-top { }

/* When scrolled from bottom */  
.scrolled-bottom { }

/* When actively scrolling */
.is-scrolling { }
```

## Visual Design Tokens

### Scrollbar Styling
```css
:root {
  --scrollbar-width: 4px;
  --scrollbar-track: transparent;
  --scrollbar-thumb: var(--border-strong);
  --scrollbar-thumb-hover: var(--muted);
  --scroll-shadow-intensity: 0.08;
}
```

### Scroll Indicators
```css
--scroll-indicator-height: 2px;
--scroll-indicator-gradient: linear-gradient(
  to bottom,
  rgba(43, 20, 32, 0.14),
  transparent
);
```

## Testing Checklist

- [ ] Body/document does not scroll when wheel/swipe anywhere
- [ ] Question list scrolls independently
- [ ] Detail pane scrolls independently  
- [ ] Timeline pane scrolls independently
- [ ] Scrollbars are slim and appear on hover
- [ ] Overscroll bounce works on Safari/iOS
- [ ] Scrollbars don't take up layout space
- [ ] Page maintains layout when resizing
- [ ] Drag handles for resizing panes still work

## Browser Support

- ✅ Chrome/Edge: Full support
- ✅ Firefox: Full support  
- ✅ Safari: Full support (with `-webkit-` prefixes)
- ✅ iOS Safari: Touch scrolling + momentum
- ✅ Chrome Android: Touch scrolling

## Performance Considerations

- Use `will-change: transform` sparingly (only during active scroll)
- Avoid `scroll` event listeners when possible (use IntersectionObserver)
- Debounce scroll shadow calculations
- Use CSS `position: sticky` for headers (GPU accelerated)

## Future Enhancements

1. **Scroll Position Memory**: Remember scroll position when navigating
2. **Smooth Scroll**: Programmatic smooth scrolling to specific items
3. **Virtual Scrolling**: For lists with 1000+ items
4. **Keyboard Navigation**: Arrow keys to scroll, Page Up/Down support

