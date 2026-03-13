/**
 * URL Parameter Hooks
 * Derives parameters from URL search params following state map pattern
 */

import { useSearchParams } from 'react-router-dom';
import { useMemo } from 'react';

export interface ListParams {
  org?: string;
  space?: string;
  q: string;
  sort: string;
  page: number;
  pageSize: number;
  filters: Record<string, string>;
}

export function useListParams(): ListParams {
  const [searchParams] = useSearchParams();
  
  return useMemo(() => {
    const filters: Record<string, string> = {};
    
    // Extract known filter keys
    const knownParams = new Set(['org', 'space', 'q', 'sort', 'page', 'pageSize', 'panel', 'range', 'compare']);
    
    searchParams.forEach((value, key) => {
      if (!knownParams.has(key)) {
        filters[key] = value;
      }
    });
    
    return {
      org: searchParams.get('org') ?? undefined,
      space: searchParams.get('space') ?? undefined,
      q: searchParams.get('q') ?? '',
      sort: searchParams.get('sort') ?? 'updated:desc',
      page: Number(searchParams.get('page') ?? 1),
      pageSize: Number(searchParams.get('pageSize') ?? 25),
      filters
    };
  }, [searchParams]);
}

export interface AdminParams extends ListParams {
  panel: 'open' | 'closed';
  range: '7d' | '30d' | '90d' | 'custom';
  compare?: string;
}

export function useAdminParams(): AdminParams {
  const [searchParams] = useSearchParams();
  const baseParams = useListParams();
  
  return useMemo(() => ({
    ...baseParams,
    panel: (searchParams.get('panel') as 'open' | 'closed') ?? 'closed',
    range: (searchParams.get('range') as '7d' | '30d' | '90d' | 'custom') ?? '7d',
    compare: searchParams.get('compare') ?? undefined
  }), [baseParams, searchParams]);
}

export function useUpdateParams() {
  const [, setSearchParams] = useSearchParams();
  
  return (updates: Record<string, string | number | undefined | null>) => {
    setSearchParams((prev) => {
      const newParams = new URLSearchParams(prev);
      
      Object.entries(updates).forEach(([key, value]) => {
        if (value === undefined || value === null || value === '') {
          newParams.delete(key);
        } else {
          newParams.set(key, String(value));
        }
      });
      
      return newParams;
    });
  };
}
