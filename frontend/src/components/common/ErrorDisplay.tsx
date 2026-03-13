/**
 * @deprecated This file is deprecated. Import from '../ui' instead:
 * 
 * import { ErrorDisplay, NetworkError, AuthError, NotFoundError, ServerError } from '../ui';
 * 
 * This file will be removed in a future version.
 */

// Re-export from the DS location for backward compatibility
export { 
  ErrorDisplay,
  NetworkError,
  AuthError,
  NotFoundError,
  ServerError,
  AccessDeniedError,
} from '../ui/error-display';

export type { ErrorDisplayProps, ErrorStateProps } from '../ui/error-display';

// Default export for backward compatibility
import { ErrorDisplay as ED } from '../ui/error-display';
export default ED;
