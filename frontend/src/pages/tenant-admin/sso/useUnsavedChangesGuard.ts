import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Tracks whether a form is dirty and guards against accidental navigation/close.
 *
 * - Registers a `beforeunload` listener when dirty.
 * - Exposes `guardedAction` to intercept close / provider-switch when dirty.
 * - Inline confirmation state lives here so sheets can render the
 *   confirmation strip in their footer without a stacked modal.
 */
export function useUnsavedChangesGuard() {
  const [isDirty, setIsDirty] = useState(false);
  const [pendingAction, setPendingAction] = useState<(() => void) | null>(null);
  const pendingContextRef = useRef<string>('');

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

  const guardedAction = useCallback(
    (action: () => void, context = 'this form') => {
      if (isDirty) {
        pendingContextRef.current = context;
        setPendingAction(() => action);
      } else {
        action();
      }
    },
    [isDirty],
  );

  const confirmDiscard = useCallback(() => {
    const action = pendingAction;
    setPendingAction(null);
    pendingContextRef.current = '';
    setIsDirty(false);
    action?.();
  }, [pendingAction]);

  const cancelDiscard = useCallback(() => {
    setPendingAction(null);
    pendingContextRef.current = '';
  }, []);

  return {
    isDirty,
    setIsDirty,
    isConfirming: pendingAction !== null,
    pendingContext: pendingContextRef.current,
    guardedAction,
    confirmDiscard,
    cancelDiscard,
  };
}
