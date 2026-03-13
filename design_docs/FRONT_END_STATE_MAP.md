# Eliza Platform — State Map & React State Best Practices (Single File)

> **Context**
> - UI: Light theme, 3‑pane app (left nav · center content/list · right details panel), text + charts, long “lists of items” (domain‑agnostic).
> - Goal: A practical state map and library choices that are framework‑agnostic on the server. Your app is in **Python**; examples use generic HTTP so you can back them with FastAPI, Flask, Django, etc.

---

## 0) Recommended Client Stack

- **Server state:** [TanStack Query (React Query)](https://tanstack.com/query/latest)
- **Global client/UI state:** [Zustand](https://github.com/pmndrs/zustand)
- **Forms:** [react-hook-form](https://react-hook-form.com/) + [Zod](https://zod.dev)
- **Routing/URL:** React Router v6 + `useSearchParams`
- **Virtualized lists:** `react-virtuoso` (or `react-window`)
- **Charts:** Recharts (simple) or Visx (custom)

> Why: Server state ≠ client state. Let React Query own fetching/caching/invalidations. Keep global UI bits tiny and selector‑driven.

---

## 1) State Ownership Matrix

| Slice | Examples | Owner | Persistence | Why |
|---|---|---|---|---|
| **Auth/session** | access token, user, orgs/roles | Zustand (`useAuth`) + secure token handling | token in memory; refresh via `httpOnly` cookie if possible | Fast checks; avoid XSS |
| **Org / workspace context** | active org/space | URL `?org=&space=` + mirror in store | URL | Shareable links, back/forward |
| **Items (list + count)** | paginated lists, totals | React Query (`['items', params]`) | cache (stale ~30s) | Server is source of truth |
| **Item detail** | single record + subresources | React Query (`['item', id]`) | cache | Decouples list/detail lifecycles |
| **Filters/sort/search** | q, sort, tags, dates | URL params + selector | URL | Durable, debuggable |
| **Selection** | selectedIds across panes | Zustand (`useSelection`) | optional (sessionStorage) | Cross‑pane ops without rerenders |
| **UI layout** | theme, panel widths, collapsed nav | Zustand (`useUI`) | localStorage (versioned) | App feel |
| **Forms/drafts** | create/update flows | react‑hook‑form (local) + optional draft in store | sessionStorage | Resilient to nav |
| **Charts data** | series in range | React Query (`['metrics', scope, range]`) | short cache | Refetch on range/filter |
| **Notifications** | toast queue | Zustand (`useToasts`) | none | Transient |
| **Background jobs** | upload/compute status | React Query (`['job', id]`) | cache + polling | Server truth |

---

## 2) URL State Schema

**Paths**
```
/app/:space/list
/app/:space/item/:id
/app/:space/analytics
```

**Query params**
- `org`, `space` — context
- `q` — search text
- `sort` — `field:dir` (e.g., `updated:desc`)
- `page`, `pageSize`
- `filters` — multi‑key or JSON‑compressed
- `panel` — `open|closed`
- `range` — `7d|30d|90d|custom`
- `compare` — optional baseline id or time window

**Rules**
- URL is the **single source of truth** for filters/sort/pagination/range.
- Derive a **params object** from the URL; feed queries/selectors from it.
- Mirror to store only for UI convenience (never as the primary source).

---

## 3) React Query Map (Server State)

**Query Keys**
```ts
// Lists
['items', { org, space, q, sort, filters, page, pageSize }]

// Detail
['item', id]

// Metrics/Charts
['metrics', { org, space, range, filters }]

// Background jobs
['job', id]

// Lookups (rare changes)
['lookups', 'tags'] // staleTime: Infinity
['lookups', 'types']
```

**Options**
- `staleTime: 30_000` for lists/detail; tune per endpoint.
- `keepPreviousData: true` for pagination and sort changes.
- Use `select:` to shape API payloads into compact view models.
- Mutations: invalidate **minimal** scopes:
  - update → `invalidateQueries(['item', id])` + matching `['items']`
  - bulk actions → `invalidateQueries(['items'])`
- Prefetch detail on row hover: `queryClient.prefetchQuery(['item', id], …)`

**Error handling**
- Centralize `onError` → toast via `useToasts`.

---

## 4) Zustand Stores (Global Client/UI)

```ts
// useAuth: session & identity
type AuthState = {
  user?: User; org?: string; space?: string;
  setCtx: (p: Partial<Pick<AuthState,'org'|'space'>>) => void;
};

// useUI: layout & theme
type UIState = {
  leftCollapsed: boolean;
  rightOpen: boolean;
  rightWidth: number; // px
  theme: 'light'|'dark';
  set: (p: Partial<UIState>) => void;
};

// useSelection: cross‑pane selection
type SelectionState = {
  ids: string[];
  set: (ids: string[]) => void;
  clear: () => void;
};

// useToasts: ephemeral notifications
type Toast = { id: string; kind: 'success'|'error'|'info'|'warning'; msg: string };
type ToastState = {
  toasts: Toast[];
  push: (t: Omit<Toast,'id'>) => void;
  dismiss: (id: string) => void;
};
```

**Rules**
- Always read via **selectors** (`useUI(s => s.rightOpen)`) to avoid rerenders.
- Persist only stable UI prefs (theme, panel widths) with `persist({ name: 'ui-v1' })`.
- Do **not** store server data here.

---

## 5) Local Component State

- Inputs, open/closed toggles, inline editors → `useState`.
- Multi‑step or complex transitions → `useReducer` (view → edit → saving → error/saved).
- Resizable splitters: keep local while dragging; persist to `useUI.rightWidth` on blur.

---

## 6) Forms & Drafts

- Use **react‑hook‑form** (uncontrolled inputs → perf) + **Zod** for validation.
- Auto‑save **drafts** (sessionStorage) keyed by route, every 2–3s (debounced).
- On submit success: invalidate relevant queries, clear draft, toast success.

**Example**
```ts
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

const schema = z.object({ name: z.string().min(1), threshold: z.number().min(0).max(1) });

export function ItemForm({ onSubmit }) {
  const { register, handleSubmit, formState:{ errors, isSubmitting } } =
    useForm({ resolver: zodResolver(schema), mode: 'onChange' });

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('name')} />
      {errors.name && <small>{errors.name.message}</small>}
      <input type=\"number\" step=\"0.01\" {...register('threshold', { valueAsNumber: true })} />
      <button disabled={isSubmitting}>Save</button>
    </form>
  );
}
```

---

## 7) State Flows (Common)

### A) Filter + Paginate “list of items”
1. User changes filter → write to **URL** (`setSearchParams`)
2. Derive **params** → React Query refetches `['items', params]`
3. `keepPreviousData: true` prevents list jump
4. Clear selection if params materially change

### B) Open item in right panel (preview)
1. Click row → set `panel=open&id=…` in URL
2. Prefetch `['item', id]` if not cached
3. Right panel reads `id` from URL, queries detail
4. Close → `panel=closed` (keep list scroll)

### C) Inline update
1. Open inline editor → local state or small form
2. `useMutation` to save (optimistic if trivial)
3. On success → invalidate detail + narrow list query
4. Toast `Saved`

### D) Charts time range
1. Change `range` select → write to URL
2. Query `['metrics', { …, range }]` refetches; fade/scale 150–200ms
3. Optionally remember per‑space range in localStorage

---

## 8) Data Shapes (Suggested)

```ts
type ItemSummary = {
  id: string; title: string; subtitle?: string;
  icon?: string; tags?: string[];
  meta?: Record<string,string|number>; // short fields for list columns
  metric?: number; // optional right-edge number
};

type Paged<T> = { data: T[]; page: number; pageSize: number; total: number };

type ItemDetail = ItemSummary & {
  description?: string; fields?: Record<string,unknown>;
  related?: ItemSummary[];
};

type SeriesPoint = { t: number; v: number };
type MetricSeries = { label: string; points: SeriesPoint[] };
```

Normalize client‑side only if you do heavy local editing; otherwise keep server‑shape and let the cache own consistency.

---

## 9) Performance Guardrails

- Virtualize long lists (>200 DOM rows) with **react‑virtuoso**.
- Use **selectors** for Zustand reads (avoid store‑wide rerenders).
- `select` in React Query to trim large payloads before components.
- `memo` row components; key by `id`.
- Debounce URL updates for text search (250–350ms).
- Prefer `keepPreviousData` over spinners for list feel; use skeletons for initial loads.

---

## 10) Telemetry, Testing, QA

- Hook into React Query `onSuccess/onError` for timing + outcome metrics.
- Feature flags: tiny Zustand slice; gate risky flows.
- **Testing**:  
  - Integration: React Testing Library + MSW (mock HTTP)  
  - Unit: store selectors & reducers  
  - E2E: Playwright—assert URL ↔ UI sync (filters, selection, open panel)
- **QA checklist**: focus rings visible; URL reflects state; back/forward works; list virtualization engaged for large sets; no duplicate state sources.

---

## 11) Copy‑Paste Scaffolds

**Params derivation (URL → object)**
```ts
export function useListParams() {
  const [sp] = useSearchParams();
  return {
    org: sp.get('org') ?? undefined,
    space: sp.get('space') ?? undefined,
    q: sp.get('q') ?? '',
    sort: sp.get('sort') ?? 'updated:desc',
    page: Number(sp.get('page') ?? 1),
    pageSize: Number(sp.get('pageSize') ?? 25),
    // parse known filter keys or decode a compressed JSON string
    filters: Object.fromEntries(sp.entries()),
  } as const;
}
```

**List query hook**
```ts
import { useQuery } from '@tanstack/react-query';

export function useItemsQuery() {
  const params = useListParams();
  return useQuery({
    queryKey: ['items', params],
    queryFn: () => fetch(`/api/items?${new URLSearchParams(params as any)}`).then(r => r.json()),
    keepPreviousData: true,
    staleTime: 30_000,
  });
}
```

**Zustand selection store**
```ts
import { create } from 'zustand';
export const useSelection = create<{ids:string[]; set:(x:string[])=>void; clear:()=>void}>(set=>({
  ids: [], set: (ids)=>set({ids}), clear: ()=>set({ids:[]})
}));
```

---

## 12) Server Notes for Python Backends

- **Endpoints** should be **idempotent** for GET and accept pagination/sorting/filter params:
  - `GET /api/items?page=&pageSize=&q=&sort=&tag=&from=&to=`
  - `GET /api/items/:id`
  - `GET /api/metrics?space=&range=&...`
- **Caching**: include `ETag`/`Last-Modified`; React Query can leverage 304s.
- **Errors**: return JSON with `code`, `message`, `details`—map to toast.
- **Long jobs**: return `202 Accepted` + `Location: /api/jobs/:id`, poll via `GET /api/jobs/:id` (status, progress).

---

## 13) TL;DR Rules

- URL holds filters/sort/range; server state lives in React Query; global UI in a tiny store.
- Don’t duplicate state; derive when possible.
- Use selectors, virtualization, and `keepPreviousData` for perf.
- Schema‑validate forms; draft auto‑save to sessionStorage.
- Invalidate **smallest** query scopes on mutations.
- Always show focus and keep contrast ≥ 4.5:1.
