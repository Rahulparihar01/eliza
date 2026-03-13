import { formatDistanceToNow, isValid, parseISO } from 'date-fns';

type NullableTimestamp = string | null | undefined;
const MIN_REASONABLE_YEAR = 2000;

interface ConnectorLikeWithTimestamps {
  updated_at?: NullableTimestamp;
  created_at?: NullableTimestamp;
}

function isReasonableDate(date: Date): boolean {
  return date.getUTCFullYear() >= MIN_REASONABLE_YEAR;
}

export function parseApiDate(value: NullableTimestamp): Date | null {
  if (!value) {
    return null;
  }

  const parsed = parseISO(value);
  if (isValid(parsed) && isReasonableDate(parsed)) {
    return parsed;
  }

  const fallback = new Date(value);
  return isValid(fallback) && isReasonableDate(fallback) ? fallback : null;
}

export function formatRelativeApiTime(value: NullableTimestamp): string {
  const date = parseApiDate(value);
  if (!date) {
    return 'just now';
  }
  return formatDistanceToNow(date, { addSuffix: true });
}

export function getConnectorActivityDate(connector: ConnectorLikeWithTimestamps): Date | null {
  return parseApiDate(connector.updated_at) ?? parseApiDate(connector.created_at);
}

export function formatConnectorActivityTime(connector: ConnectorLikeWithTimestamps): string {
  const date = getConnectorActivityDate(connector);
  if (!date) {
    return 'just now';
  }
  return formatDistanceToNow(date, { addSuffix: true });
}
