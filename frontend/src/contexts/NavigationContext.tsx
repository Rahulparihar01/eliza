/**
 * NavigationContext - Contextual Sidebar Navigation State
 * 
 * Manages the state for contextual sidebar navigation where clicking
 * a section (like Platform Settings) hides the main sidebar and
 * reveals a contextual sub-navigation panel.
 * 
 * Uses SidebarMode from the design system:
 * - 'expanded': Full sidebar visible
 * - 'collapsed': Icon-only sidebar
 * - 'hidden': Sidebar completely hidden (for contextual navigation)
 */

import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getSectionFromPath } from '../components/navigation/sectionConfigs';
import type { SidebarMode } from '../components/ui/sidebar';

/* ============================================
   Types
   ============================================ */

export type ActiveSection = 
  | 'ai-recruiter' 
  | 'chat'
  | 'ai-console'
  | 'admin-settings' 
  | 'platform-settings' 
  | null;

interface NavigationContextValue {
  /** Currently active section (shows context panel when set) */
  activeSection: ActiveSection
  /** Set the active section (hides main sidebar) */
  setActiveSection: (section: ActiveSection) => void
  /** Current sidebar mode */
  sidebarMode: SidebarMode
  /** Set sidebar mode directly */
  setSidebarMode: (mode: SidebarMode) => void
  /** Clear section and navigate back to where user came from */
  clearSection: () => void
  /** Whether the sidebar is hidden (convenience) */
  isSidebarHidden: boolean
  /** The path to return to when clearing section */
  returnPath: string | null
}

/* ============================================
   Context
   ============================================ */

const NavigationContext = createContext<NavigationContextValue | undefined>(undefined);

/* ============================================
   Hook
   ============================================ */

export function useNavigation(): NavigationContextValue {
  const context = useContext(NavigationContext);
  if (!context) {
    throw new Error('useNavigation must be used within a NavigationProvider');
  }
  return context;
}

/* ============================================
   Provider
   ============================================ */

interface NavigationProviderProps {
  children: React.ReactNode;
  defaultMode?: SidebarMode;
}

export function NavigationProvider({ children, defaultMode = 'expanded' }: NavigationProviderProps) {
  const [activeSection, setActiveSectionState] = useState<ActiveSection>(null);
  const [sidebarMode, setSidebarMode] = useState<SidebarMode>(defaultMode);
  const [previousMode, setPreviousMode] = useState<SidebarMode>(defaultMode);
  const [returnPath, setReturnPath] = useState<string | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  
  // Track the previous path to know where to return to
  const previousPathRef = useRef<string | null>(null);

  // Set active section and hide sidebar
  const setActiveSection = useCallback((section: ActiveSection) => {
    if (section) {
      // Save current mode and path to restore later
      setPreviousMode(sidebarMode);
      setSidebarMode('hidden');
      // Save current path as return destination
      setReturnPath(location.pathname);
    } else {
      // Restore previous mode
      setSidebarMode(previousMode);
    }
    setActiveSectionState(section);
  }, [sidebarMode, previousMode, location.pathname]);

  // Clear section, restore sidebar, and navigate back
  const clearSection = useCallback(() => {
    const pathToReturn = returnPath || '/home';
    setActiveSectionState(null);
    setSidebarMode(previousMode);
    setReturnPath(null);
    // Navigate back to where user came from
    navigate(pathToReturn);
  }, [previousMode, returnPath, navigate]);

  // Auto-detect section from URL on mount and route changes
  useEffect(() => {
    const detectedSection = getSectionFromPath(location.pathname);
    const previousSection = previousPathRef.current ? getSectionFromPath(previousPathRef.current) : null;
    
    if (detectedSection && detectedSection !== activeSection) {
      // Entering a new section - save the previous path as return destination
      // Only save if we're coming from a non-section page (like home)
      if (!previousSection && previousPathRef.current) {
        setReturnPath(previousPathRef.current);
      }
      setActiveSectionState(detectedSection);
      setPreviousMode(sidebarMode);
      setSidebarMode('hidden');
    }
    
    // Update previous path ref
    previousPathRef.current = location.pathname;
    // Don't auto-clear when navigating away - let user explicitly go back
  }, [location.pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  const value: NavigationContextValue = {
    activeSection,
    setActiveSection,
    sidebarMode,
    setSidebarMode,
    clearSection,
    isSidebarHidden: sidebarMode === 'hidden',
    returnPath,
  };

  return (
    <NavigationContext.Provider value={value}>
      {children}
    </NavigationContext.Provider>
  );
}

export default NavigationContext;
