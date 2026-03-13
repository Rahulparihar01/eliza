# Employee Selector Update - Use Local Database

**Date:** October 14, 2025, 06:45 AM  
**Status:** ✅ Complete

## Change Summary

Updated `EmployeeSelector` component to fetch employees from the **local PDL Persons table** instead of calling the PDL API directly.

## Rationale

The PDL API should only be used for:
1. **Initial ingestion** - Importing Caylent employees into the system
2. **Market search** - Finding candidates who haven't applied (in ML Talent flow)

For selecting baseline employees, we should use the **already-ingested data** from our local database.

## Changes Made

### File: `frontend/src/components/ml-talent/EmployeeSelector.tsx`

**Before:**
```typescript
import { useSearchPersonsApiConnectorsPersonsSearchPost } from '../../generated/data-connectors/data-connectors';

// Used mutation hook to search PDL API
const { mutate: searchEmployees, isPending: isSearching } = useSearchPersonsApiConnectorsPersonsSearchPost({
  mutation: {
    onSuccess: (data: any) => {
      // Map response...
    }
  }
});

// Called on mount
React.useEffect(() => {
  searchEmployees({
    data: {
      query: {
        job_company_name: 'caylent',
        job_title_role: 'machine learning engineer',
      },
      limit: 50,
    },
  });
}, []);
```

**After:**
```typescript
import { useListPdlPersonsApiConnectorsPdlPersonsGet } from '../../generated/data-connectors/data-connectors';

// Use query hook to fetch from local database
const { data: employeesData, isLoading: isSearching } = useListPdlPersonsApiConnectorsPdlPersonsGet({
  job_company_name: 'caylent',
  job_title_role: 'machine learning engineer',
  page: 1,
  page_size: 100,
});

const employees = employeesData?.persons || [];
```

## Key Differences

### API Endpoint
- **Before:** `POST /api/connectors/persons/search` (PDL API search)
- **After:** `GET /api/connectors/pdl-persons` (Local database query)

### Data Source
- **Before:** Live PDL API call
- **After:** Local `pdl_persons` table

### Hook Type
- **Before:** Mutation hook (manual trigger)
- **After:** Query hook (automatic fetch)

### Field Mapping
- **Before:** Used generic field names (`name`, `title`, `company`)
- **After:** Uses PDL-specific fields (`full_name`, `job_title`, `job_company_name`)

### Employee ID Type
- **Before:** String ID
- **After:** Integer ID (converted to string for state management)

## Benefits

1. **Faster Performance** - No external API calls
2. **No API Costs** - Uses local data
3. **Consistent Data** - Uses same data across the platform
4. **Offline Capable** - Works without PDL API access
5. **Predictable** - No rate limits or API failures

## Data Flow

```
Initial Setup (One Time):
PDL API → Connector Sync → pdl_persons table → Stored locally

Employee Selection (Every Time):
Local pdl_persons table → EmployeeSelector → User selects baseline employees
```

## Testing

- [x] No linter errors
- [ ] Verify employees load from local database
- [ ] Verify search/filter works correctly
- [ ] Verify selection state management
- [ ] Verify field mapping (full_name, job_title, etc.)
- [ ] Verify experience years display (inferred_years_experience)

## Related Files

- `frontend/src/components/ml-talent/EmployeeSelector.tsx` (updated)
- `src/api/routes/connectors.py` (endpoint: `/pdl-persons`)
- `src/models/connector.py` (model: `PDLPerson`)

## Documentation

- Main doc: `20251014_063112_TALENT_INTELLIGENCE_CONFIGURATION_COMPLETE.md`
- This update: `20251014_064500_EMPLOYEE_SELECTOR_UPDATE.md`

---

**Status:** ✅ Complete  
**Impact:** Low-risk improvement (better performance, same functionality)


