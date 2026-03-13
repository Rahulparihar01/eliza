# Vector Search Admin Settings Feature

## Overview

Admins can now configure vector search parameters (similarity threshold and result limit) through the Admin Settings page. These settings are persisted in the database and automatically applied to all document searches performed by the BI agents.

## Feature Components

### 1. Backend Service Layer

**File**: `src/services/settings_service.py`

Added methods to `SettingsService`:
- `get_vector_search_similarity_threshold()` - Returns threshold (default: 0.5)
- `set_vector_search_similarity_threshold(threshold)` - Sets threshold (0.0-1.0)
- `get_vector_search_result_limit()` - Returns limit (default: 10)
- `set_vector_search_result_limit(limit)` - Sets limit (1-100)

### 2. API Endpoints

**File**: `src/api/routes/settings.py`

**GET** `/v1/settings/vector-search/config`
- Returns current vector search configuration
- Response:
  ```json
  {
    "similarity_threshold": 0.5,
    "result_limit": 10
  }
  ```

**PUT** `/v1/settings/vector-search/config`
- Updates vector search configuration (admin only)
- Request body:
  ```json
  {
    "similarity_threshold": 0.5,  // optional, 0.0-1.0
    "result_limit": 10            // optional, 1-100
  }
  ```
- Response: Updated configuration

### 3. DataAnalysisFlow Integration

**File**: `src/crewai_flows/data_analysis_flow.py`

The `retrieve_data` method now:
1. Fetches vector search settings from the database
2. Applies them to `DocumentSearchTool` initialization
3. All searches use the admin-configured values

**Before** (hardcoded):
```python
doc_tool = DocumentSearchTool(
    company_hr_dataset=self.state.company_hr_dataset,
    limit=10,
    similarity_threshold=0.5
)
```

**After** (dynamic):
```python
settings_service = SettingsService(db)
vector_threshold = settings_service.get_vector_search_similarity_threshold()
vector_limit = settings_service.get_vector_search_result_limit()

doc_tool = DocumentSearchTool(
    company_hr_dataset=self.state.company_hr_dataset,
    limit=vector_limit,
    similarity_threshold=vector_threshold
)
```

### 4. Admin Settings UI

**File**: `frontend/src/pages/admin/AdminSettingsPage.tsx`

New section: **Vector Search Configuration**

#### Display Mode (Non-Editing)
Shows two cards:
1. **Similarity Threshold** - Current value (0.0-1.0)
2. **Result Limit (k)** - Current max results

#### Edit Mode
Provides:
- Number inputs with validation
- Quick-select buttons for recommended values:
  - **Threshold**: 0.3 (Broad), 0.5 (Balanced), 0.7 (Strict)
  - **Limit**: 5 (Fast), 10 (Balanced), 20 (Comprehensive)
- Real-time validation with user-friendly error messages
- Save/Cancel buttons

## Understanding the Parameters

### Similarity Threshold

**What it controls**: Minimum cosine similarity score (0.0-1.0) for a document chunk to be included in search results.

**How it works**:
- Vector embeddings are compared using cosine similarity
- Score of 1.0 = identical vectors
- Score of 0.0 = completely orthogonal vectors

**Recommended values**:
- **0.3-0.4**: Very broad search, many results (good for exploration)
- **0.5-0.6**: Balanced (good default for most use cases)
- **0.7-0.8**: Strict search, only highly relevant results
- **0.9+**: Near-exact matches only (very restrictive)

**Current default**: `0.5`

### Result Limit (k value)

**What it controls**: Maximum number of document chunks returned from vector search.

**How it works**:
- FAISS returns top-k nearest neighbors
- More results = more context for agents, but slower processing
- Fewer results = faster but may miss relevant information

**Recommended values**:
- **5-7**: Fast searches, focused results
- **10-15**: Good balance (default)
- **20-30**: Comprehensive searches, more context
- **50+**: Very thorough but slow (use sparingly)

**Current default**: `10`

## Testing Guide

### 1. Test API Directly

```bash
# Get current settings (requires admin auth)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5001/v1/settings/vector-search/config

# Update settings
curl -X PUT \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"similarity_threshold": 0.4, "result_limit": 15}' \
  http://localhost:5001/v1/settings/vector-search/config
```

### 2. Test via Admin UI

1. Navigate to **Admin Settings** (from navigation menu)
2. Scroll to **Vector Search Configuration** section
3. Click **Edit Settings**
4. Try different values or use quick-select buttons
5. Click **Save Changes**
6. Verify the new values are displayed
7. Submit a new BI question
8. Check `bi_tool_executions` table to verify:
   ```sql
   SELECT tool_output::json->'search_metadata'
   FROM bi_tool_executions
   WHERE tool_name = 'Document Semantic Search'
   ORDER BY created_at DESC
   LIMIT 1;
   ```

### 3. Test Effect on Search Results

**Scenario 1: Lower threshold (0.3)**
- Submit a BI question about "database"
- Should return MORE results (broader search)

**Scenario 2: Higher threshold (0.7)**
- Submit the same question
- Should return FEWER results (stricter search)

**Scenario 3: Increase limit (20)**
- Should return more chunks (if available)

**Scenario 4: Decrease limit (5)**
- Should return exactly 5 chunks max

## Database Schema

Settings are stored in the `system_settings` table:

```sql
-- Similarity threshold setting
INSERT INTO system_settings (setting_key, setting_value, setting_type, description)
VALUES (
  'vector_search_similarity_threshold',
  '0.5',
  'float',
  'Minimum similarity score (0.0-1.0) for document search results'
);

-- Result limit setting
INSERT INTO system_settings (setting_key, setting_value, setting_type, description)
VALUES (
  'vector_search_result_limit',
  '10',
  'integer',
  'Maximum number of document chunks to return from vector search (k value)'
);
```

## Permission Requirements

- **Read settings**: Any authenticated user (for the config endpoint)
- **Update settings**: `settings:write` permission (admin only)

The Admin Settings page is accessible to users with:
- `settings:read` OR
- `system:admin` OR
- `users:read`

## Impact on Existing Functionality

### Before This Feature
- Vector search used hardcoded values (threshold=0.7, limit=10)
- Changes required code modification and deployment

### After This Feature
- Settings are configurable via UI
- Changes take effect immediately for new searches
- No code deployment needed for tuning

## Production Considerations

### Performance
- Reading settings adds ~1 database query per BI question
- Impact is negligible (settings service uses connection pooling)
- Settings could be cached if needed (future optimization)

### Monitoring
- Watch `bi_tool_executions.results_count` to see if threshold is too strict (0 results)
- If searches return 0 results consistently, lower the threshold
- If searches return too many irrelevant results, raise the threshold

### Recommended Starting Values
- **Production**: `threshold=0.5, limit=10` (balanced)
- **Development**: `threshold=0.4, limit=15` (more exploratory)
- **Demo**: `threshold=0.6, limit=5` (fast and focused)

## Future Enhancements

1. **Per-Company Settings**: Allow different thresholds for different companies
2. **Query-Specific Overrides**: Allow users to adjust search strictness per question
3. **Auto-Tuning**: Automatically adjust threshold based on result relevance
4. **A/B Testing**: Test different settings to find optimal values
5. **Settings History**: Track changes to settings over time
6. **Performance Metrics**: Show average search time and result counts

## Troubleshooting

### Issue: Settings not taking effect

**Check**:
1. Verify settings are saved in database:
   ```sql
   SELECT * FROM system_settings WHERE setting_key LIKE 'vector_search%';
   ```
2. Restart celery-worker:
   ```bash
   docker-compose restart celery-worker
   ```
3. Check celery logs for errors:
   ```bash
   docker-compose logs celery-worker --tail=50
   ```

### Issue: Searches returning 0 results

**Solution**: Lower the similarity threshold
- Try `0.4` first, then `0.3` if still no results
- Check if documents are properly indexed:
  ```sql
  SELECT COUNT(*) FROM document_chunks WHERE document_id IN (
    SELECT id FROM documents WHERE company_hr_dataset = 'your_company'
  );
  ```

### Issue: Searches too slow

**Solution**: Reduce the result limit
- Try `limit=5` for faster searches
- Consider optimizing chunk sizes if this is a persistent issue

## Related Documentation

- [Agent Activity Capture](./AGENT_ACTIVITY_CAPTURE_SPECIFICATION.md) - How tool executions are tracked
- [Document Search Company Fix](./DOCUMENT_SEARCH_COMPANY_FIX.md) - How company filtering works
- [API Consolidation](./API_CONSOLIDATION.md) - General API design patterns

## Summary

This feature provides admins with fine-grained control over vector search behavior, enabling them to tune search performance and relevance without code changes. The settings are persisted, immediately effective, and apply system-wide to all BI questions.

