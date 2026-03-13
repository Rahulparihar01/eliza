# Multi-Source Person Data Architecture

**Date:** October 9, 2025  
**Purpose:** Design for ingesting person data from multiple sources into unified Person model  
**Status:** Architecture Design

---

## Executive Summary

**Question:** How do we handle person data from multiple sources (PDL, LinkedIn, Clearbit, ZoomInfo, etc.) while maintaining a unified "Person" representation?

**Answer:** We need to evolve from source-specific models (`PDLPerson`) to a **Master Data Management (MDM) pattern** with:
1. A unified `Person` master record
2. Source-specific `PersonDataSource` records for provenance
3. Intelligent merge/deduplication logic
4. Field-level data quality scoring
5. A "golden record" strategy

---

## Current State Analysis

### ✅ What Works Well

1. **Generic Search Infrastructure**
   - `BaseElasticsearchSync` and `BaseNeo4jSync` are data-source agnostic
   - Configuration-driven (YAML)
   - Works with ANY dataset

2. **Staging Pattern**
   - `IngestedData` table captures raw JSON from any source
   - Source attribution tracked (`source_record_id`, `source_record_type`)
   - Company dataset tracking (`company_dataset`)

3. **Transformation Pattern**
   - `PDLTransformer` normalizes PDL data
   - Pattern is reusable for other sources

4. **Async Sync Pattern**
   - PostgreSQL → Elasticsearch + Neo4j
   - Non-blocking, resilient
   - Reusable for any person source

### ⚠️ Current Limitations

1. **Source-Specific Model**
   ```python
   class PDLPerson(BaseModel):
       pdl_id = Column(String(100), nullable=False)  # ❌ PDL-specific
       # ... other fields
   ```
   - Table name: `pdl_persons` (source in name)
   - Primary key: `pdl_id` (source-specific ID)
   - No way to link same person from different sources

2. **No Multi-Source Support**
   - Can't merge data from LinkedIn + PDL for same person
   - No deduplication across sources
   - No provenance tracking (which source provided which field)

3. **No Data Quality Management**
   - All fields treated equally regardless of source quality
   - No confidence scores
   - No "golden record" logic

---

## Challenges with Multiple Sources

### 1. Different Schemas
```
PDL:                  LinkedIn:              Clearbit:
- pdl_id              - linkedin_id          - clearbit_id
- full_name           - firstName +          - name
- job_title             lastName             - title
- job_company_name    - currentCompany      - employment.name
- skills: [...]       - skills: [...]       - tech: [...]
```

### 2. Field Name Variations
- `job_title` vs `currentTitle` vs `title`
- `job_company_name` vs `currentCompany` vs `employment.name`
- `skills` vs `endorsedSkills` vs `tech`

### 3. Data Quality Differences
- PDL: High confidence, comprehensive
- LinkedIn scraping: Medium confidence, might be stale
- Clearbit: Company-focused, person data secondary

### 4. Overlapping Records
- Same person in multiple sources
- Need to merge without duplicating
- Determine "best" value for each field

### 5. Update Frequency
- PDL: Updated monthly
- LinkedIn: Real-time if scraping
- Clearbit: Updated on company changes

---

## Proposed Architecture

### High-Level Pattern: Master Data Management (MDM)

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATA SOURCES                                 │
│                                                                   │
│   PDL API      LinkedIn      Clearbit      ZoomInfo             │
│      ↓             ↓            ↓              ↓                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│               STAGING (Source-Agnostic)                          │
│                                                                   │
│   IngestedData                                                   │
│   - source_record_id = "pdl_abc123" or "li_xyz789"             │
│   - source_record_type = "person"                               │
│   - raw_data = {full JSON from source}                          │
│   - metadata = {"source": "pdl", "confidence": 9}               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│           TRANSFORMATION (Source-Specific Transformers)          │
│                                                                   │
│   PDLTransformer     LinkedInTransformer     ClearbitTransformer│
│        ↓                     ↓                        ↓          │
│    Normalized            Normalized              Normalized      │
│    Person Data          Person Data            Person Data       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              MASTER DATA LAYER (Unified Model)                   │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ Person (Master Record - "Golden Record")               │    │
│  │ - person_id (UUID, source-agnostic)                    │    │
│  │ - full_name (best value from all sources)              │    │
│  │ - job_title (best value)                               │    │
│  │ - ... (merged fields)                                  │    │
│  └────────────────────────────────────────────────────────┘    │
│                           ↓                                       │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ PersonDataSource (Provenance)                           │    │
│  │ - person_id → Person                                    │    │
│  │ - source_name = "pdl"                                   │    │
│  │ - source_record_id = "pdl_abc123"                       │    │
│  │ - source_data = {all fields from this source}           │    │
│  │ - confidence_score = 9                                  │    │
│  │ - last_updated = "2024-10-01"                           │    │
│  └────────────────────────────────────────────────────────┘    │
│                           ↓                                       │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ PersonFieldProvenance                                   │    │
│  │ - person_id                                             │    │
│  │ - field_name = "job_title"                              │    │
│  │ - source_name = "pdl"                                   │    │
│  │ - field_value = "Senior Data Engineer"                 │    │
│  │ - confidence_score = 9                                  │    │
│  │ - last_updated = "2024-10-01"                           │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              SEARCH LAYER (Already Generic!)                     │
│                                                                   │
│   Elasticsearch      Neo4j           PostgreSQL (fallback)       │
│   (full-text)        (graph)                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Detailed Database Schema

### 1. Person (Master Record)

```python
class Person(BaseModel):
    """
    Unified person record merged from multiple data sources.
    
    This is the "golden record" - the best representation of a person
    combining data from all available sources.
    """
    __tablename__ = "persons"
    
    # Identity (source-agnostic)
    person_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)
    
    # Basic info (best value from all sources)
    full_name = Column(String(255), nullable=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    
    # Current employment (best value)
    job_title = Column(String(255), nullable=True, index=True)
    job_company_name = Column(String(255), nullable=True, index=True)
    job_company_id = Column(String(100), nullable=True)
    job_start_date = Column(String(50), nullable=True)
    
    # Contact info (best value)
    primary_email = Column(String(255), nullable=True, index=True)
    emails = Column(JSON, nullable=True)  # All unique emails from all sources
    
    # Social profiles (merged from all sources)
    linkedin_url = Column(String(500), nullable=True, index=True)
    twitter_url = Column(String(500), nullable=True)
    github_url = Column(String(500), nullable=True)
    
    # Location (best value)
    location_name = Column(String(255), nullable=True)
    location_country = Column(String(100), nullable=True, index=True)
    
    # Skills (union of all sources)
    skills = Column(JSON, nullable=True)  # Merged, deduplicated skills
    
    # Experience
    inferred_years_experience = Column(Integer, nullable=True)
    work_history = Column(JSON, nullable=True)  # Merged work history
    education_history = Column(JSON, nullable=True)  # Merged education
    
    # Data quality metrics
    completeness_score = Column(Float, nullable=True)  # 0-1, % of fields populated
    confidence_score = Column(Float, nullable=True)  # 0-1, overall confidence
    last_enriched_at = Column(DateTime(timezone=True), nullable=True)
    
    # Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    data_sources = relationship("PersonDataSource", back_populates="person", cascade="all, delete-orphan")
    field_provenance = relationship("PersonFieldProvenance", back_populates="person", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_person_customer', 'customer_id', 'person_id'),
        Index('ix_person_name', 'first_name', 'last_name'),
        Index('ix_person_company', 'job_company_name', 'job_title'),
        Index('ix_person_email', 'primary_email'),
        {'extend_existing': True}
    )
```

### 2. PersonDataSource (Provenance)

```python
class PersonDataSource(BaseModel):
    """
    Tracks which data sources contributed to a Person record.
    
    Enables:
    - Provenance tracking (where did this data come from?)
    - Re-processing (if source data updated)
    - Data quality comparison
    """
    __tablename__ = "person_data_sources"
    
    id = Column(Integer, primary_key=True)
    
    # Links to master person
    person_id = Column(UUID(as_uuid=True), ForeignKey("persons.person_id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)
    
    # Source identification
    source_name = Column(String(50), nullable=False, index=True)  # "pdl", "linkedin", "clearbit"
    source_record_id = Column(String(255), nullable=False, index=True)  # External ID from source
    
    # Raw data from this source
    source_data = Column(JSON, nullable=False)  # Full record from source
    
    # Quality metrics
    confidence_score = Column(Float, nullable=True)  # Source's confidence (if available)
    completeness_score = Column(Float, nullable=True)  # % of fields this source provided
    
    # Status
    is_primary_source = Column(Boolean, default=False)  # Is this the "authoritative" source?
    is_active = Column(Boolean, default=True)  # Can we still update from this source?
    
    # Tracking
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    sync_count = Column(Integer, default=1)  # How many times updated from this source
    
    # Reference to staging
    ingested_data_id = Column(Integer, ForeignKey("ingested_data.id"), nullable=True)
    
    # Relationships
    person = relationship("Person", back_populates="data_sources")
    
    __table_args__ = (
        Index('ix_pds_person', 'person_id', 'source_name'),
        Index('ix_pds_source_id', 'source_name', 'source_record_id'),
        # Unique: Same source + source_record_id should only exist once per person
        UniqueConstraint('person_id', 'source_name', 'source_record_id', name='uq_person_source'),
        {'extend_existing': True}
    )
```

### 3. PersonFieldProvenance (Field-Level Tracking)

```python
class PersonFieldProvenance(BaseModel):
    """
    Tracks which source provided which field value.
    
    Enables:
    - Field-level provenance (who said job_title = "Senior Engineer"?)
    - Conflict resolution (PDL says X, LinkedIn says Y, use PDL)
    - Historical tracking (field value changes over time)
    """
    __tablename__ = "person_field_provenance"
    
    id = Column(Integer, primary_key=True)
    
    # Links
    person_id = Column(UUID(as_uuid=True), ForeignKey("persons.person_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Field identification
    field_name = Column(String(100), nullable=False, index=True)  # "job_title", "skills", etc.
    field_path = Column(String(255), nullable=True)  # For nested: "work_history[0].company"
    
    # Source of this field value
    source_name = Column(String(50), nullable=False, index=True)  # "pdl", "linkedin"
    
    # Value (stored as JSON for flexibility)
    field_value = Column(JSON, nullable=True)
    
    # Quality
    confidence_score = Column(Float, nullable=True)  # How confident is this value?
    is_current_value = Column(Boolean, default=True)  # Is this the value in Person table?
    
    # Tracking
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    person = relationship("Person", back_populates="field_provenance")
    
    __table_args__ = (
        Index('ix_pfp_person_field', 'person_id', 'field_name'),
        Index('ix_pfp_source', 'source_name', 'field_name'),
        {'extend_existing': True}
    )
```

---

## Implementation Plan

### Phase 1: Add New Tables (No Breaking Changes)

**Goal:** Add new Person tables alongside existing PDLPerson

**Steps:**
1. Create migration for `persons`, `person_data_sources`, `person_field_provenance` tables
2. Keep `pdl_persons` table (no changes to existing data)
3. Run migration

**Result:** New tables exist, old data still works

### Phase 2: Create Unified Transformer

**Goal:** Build `PersonMergeService` to create unified Person records

**File:** `src/services/ingestion/person_merge_service.py`

```python
class PersonMergeService:
    """
    Merges person data from multiple sources into unified Person record.
    
    Strategy:
    1. Match/Link: Determine if person already exists
    2. Merge: Combine data from all sources
    3. Resolve Conflicts: Pick best value per field
    4. Track Provenance: Record where each value came from
    """
    
    def merge_person(
        self,
        source_name: str,
        source_record_id: str,
        source_data: Dict[str, Any],
        customer_id: str
    ) -> Person:
        """
        Merge person data into master Person record.
        
        Args:
            source_name: "pdl", "linkedin", "clearbit"
            source_record_id: External ID from source
            source_data: Normalized person data from transformer
            customer_id: Customer ID
            
        Returns:
            Merged Person record
        """
        # 1. Try to find existing person
        person = self._find_existing_person(source_data, customer_id)
        
        if not person:
            # Create new master person
            person = Person(
                customer_id=customer_id,
                created_at=datetime.utcnow()
            )
            self.db.add(person)
            self.db.flush()  # Get person_id
        
        # 2. Add/update data source record
        data_source = self._upsert_data_source(
            person.person_id,
            source_name,
            source_record_id,
            source_data,
            customer_id
        )
        
        # 3. Merge fields using conflict resolution
        self._merge_fields(person, source_name, source_data)
        
        # 4. Update quality scores
        self._update_quality_scores(person)
        
        self.db.commit()
        return person
    
    def _find_existing_person(
        self, 
        source_data: Dict, 
        customer_id: str
    ) -> Optional[Person]:
        """
        Find existing person using matching rules.
        
        Matching strategies (in priority order):
        1. Email match (high confidence)
        2. LinkedIn URL match (high confidence)
        3. Name + Company match (medium confidence)
        4. Fuzzy name + location match (low confidence)
        """
        # Strategy 1: Email match
        email = source_data.get('primary_email')
        if email:
            person = self.db.query(Person).filter(
                Person.customer_id == customer_id,
                Person.primary_email == email
            ).first()
            if person:
                return person
        
        # Strategy 2: LinkedIn URL match
        linkedin_url = source_data.get('linkedin_url')
        if linkedin_url:
            person = self.db.query(Person).filter(
                Person.customer_id == customer_id,
                Person.linkedin_url == linkedin_url
            ).first()
            if person:
                return person
        
        # Strategy 3: Name + Company match
        full_name = source_data.get('full_name')
        company = source_data.get('job_company_name')
        if full_name and company:
            person = self.db.query(Person).filter(
                Person.customer_id == customer_id,
                Person.full_name.ilike(f"%{full_name}%"),
                Person.job_company_name == company
            ).first()
            if person:
                return person
        
        # No match found
        return None
    
    def _merge_fields(
        self,
        person: Person,
        source_name: str,
        source_data: Dict[str, Any]
    ):
        """
        Merge fields from source into person.
        
        Conflict resolution strategy:
        1. If field is empty in Person, use source value
        2. If both have values, use "best" value based on:
           - Source priority (PDL > LinkedIn > Clearbit)
           - Confidence scores
           - Recency
        """
        # Define source priority
        source_priority = {
            'pdl': 10,
            'linkedin': 8,
            'clearbit': 6,
            'zoominfo': 7
        }
        
        for field_name, source_value in source_data.items():
            if source_value is None:
                continue
            
            current_value = getattr(person, field_name, None)
            
            # Strategy 1: Empty field, use source
            if current_value is None:
                setattr(person, field_name, source_value)
                self._track_field_provenance(
                    person.person_id,
                    field_name,
                    source_name,
                    source_value,
                    is_current=True
                )
                continue
            
            # Strategy 2: Field has value, compare quality
            # Get current field's source
            current_provenance = self.db.query(PersonFieldProvenance).filter(
                PersonFieldProvenance.person_id == person.person_id,
                PersonFieldProvenance.field_name == field_name,
                PersonFieldProvenance.is_current_value == True
            ).first()
            
            if current_provenance:
                current_priority = source_priority.get(current_provenance.source_name, 0)
                new_priority = source_priority.get(source_name, 0)
                
                # Higher priority source wins
                if new_priority > current_priority:
                    # Mark old provenance as not current
                    current_provenance.is_current_value = False
                    
                    # Update person field
                    setattr(person, field_name, source_value)
                    
                    # Track new provenance
                    self._track_field_provenance(
                        person.person_id,
                        field_name,
                        source_name,
                        source_value,
                        is_current=True
                    )
    
    def _track_field_provenance(
        self,
        person_id: UUID,
        field_name: str,
        source_name: str,
        field_value: Any,
        is_current: bool = True
    ):
        """Track which source provided which field value."""
        provenance = PersonFieldProvenance(
            person_id=person_id,
            field_name=field_name,
            source_name=source_name,
            field_value=field_value,
            is_current_value=is_current,
            first_seen_at=datetime.utcnow()
        )
        self.db.add(provenance)
```

### Phase 3: Update Transformers

**Update PDLTransformer:**
```python
class PDLTransformer:
    def transform(self, records: List[Dict]) -> Dict[str, Any]:
        # ... existing code ...
        
        # NEW: Also create/update unified Person record
        person_merge_service = PersonMergeService(self.db)
        
        for record in records:
            # 1. Create PDLPerson (existing behavior)
            pdl_person = self._transform_to_pdl_person(record)
            self._upsert_person(pdl_person)
            
            # 2. Create unified Person (NEW)
            person = person_merge_service.merge_person(
                source_name="pdl",
                source_record_id=record['id'],
                source_data=pdl_person,  # Normalized data
                customer_id=self.customer_id
            )
            
            # 3. Sync unified Person to search
            self._trigger_search_sync(person.id, self.customer_id)
```

**Create LinkedInTransformer:**
```python
class LinkedInTransformer(BaseTransformer):
    """Transform LinkedIn data to unified Person format."""
    
    def transform(self, records: List[Dict]) -> Dict[str, Any]:
        person_merge_service = PersonMergeService(self.db)
        
        for record in records:
            # Normalize LinkedIn data
            normalized_data = self._normalize_linkedin_data(record)
            
            # Merge into unified Person
            person = person_merge_service.merge_person(
                source_name="linkedin",
                source_record_id=record['linkedin_id'],
                source_data=normalized_data,
                customer_id=self.customer_id
            )
            
            # Sync to search
            self._trigger_search_sync(person.id, self.customer_id)
    
    def _normalize_linkedin_data(self, record: Dict) -> Dict:
        """Normalize LinkedIn schema to our Person schema."""
        return {
            'full_name': f"{record['firstName']} {record['lastName']}",
            'first_name': record['firstName'],
            'last_name': record['lastName'],
            'job_title': record.get('currentTitle'),
            'job_company_name': record.get('currentCompany'),
            'linkedin_url': record.get('profileUrl'),
            'skills': record.get('skills', []),
            # ... map other fields
        }
```

### Phase 4: Update Search Sync

**Update PersonSearchService to use unified Person:**
```python
class PersonSearchService:
    def _convert_person_to_document(self, person: Person) -> Dict:
        """Convert Person to Elasticsearch document."""
        return {
            'person_id': str(person.person_id),
            'customer_id': person.customer_id,
            'full_name': person.full_name,
            'job_title': person.job_title,
            'job_company_name': person.job_company_name,
            'skills': person.skills,
            'confidence_score': person.confidence_score,
            # Include source information
            'data_sources': [
                {'name': ds.source_name, 'confidence': ds.confidence_score}
                for ds in person.data_sources
            ]
        }
```

### Phase 5: Migration Path

**Migrate existing PDL data:**
```python
def migrate_pdl_to_unified_persons():
    """One-time migration: PDLPerson → Person"""
    db = SessionLocal()
    person_merge_service = PersonMergeService(db)
    
    pdl_persons = db.query(PDLPerson).all()
    
    for pdl_person in pdl_persons:
        # Convert PDLPerson to dict
        source_data = {
            'full_name': pdl_person.full_name,
            'job_title': pdl_person.job_title,
            # ... all fields
        }
        
        # Merge into unified Person
        person = person_merge_service.merge_person(
            source_name="pdl",
            source_record_id=pdl_person.pdl_id,
            source_data=source_data,
            customer_id=pdl_person.customer_id
        )
        
        print(f"Migrated PDL person {pdl_person.pdl_id} → Person {person.person_id}")
    
    db.commit()
```

---

## Conflict Resolution Rules

### Priority-Based Resolution

```python
SOURCE_PRIORITY = {
    'pdl': 10,           # Highest quality, most comprehensive
    'zoominfo': 8,       # Good quality, B2B focused
    'linkedin': 7,       # Good for current employment
    'clearbit': 6,       # Company-focused
    'web_scraping': 3,   # Lower confidence
}
```

### Field-Specific Rules

```python
FIELD_RESOLUTION_RULES = {
    'primary_email': {
        'strategy': 'most_recent',  # Use most recent valid email
        'validation': lambda x: '@' in x
    },
    
    'job_title': {
        'strategy': 'highest_priority',  # PDL > LinkedIn > Clearbit
        'prefer_source': 'pdl'
    },
    
    'skills': {
        'strategy': 'union',  # Combine skills from all sources
        'deduplicate': True,
        'normalize': lambda x: x.lower().strip()
    },
    
    'work_history': {
        'strategy': 'merge_timelines',  # Merge work histories by date
        'deduplicate_by': 'company_name'
    },
    
    'linkedin_url': {
        'strategy': 'first_valid',  # First non-empty LinkedIn URL
        'validation': lambda x: 'linkedin.com' in x
    }
}
```

---

## Benefits of This Architecture

### 1. Unified Person Model ✅
- Single source of truth for person data
- Consistent schema across all sources
- Easy to query and analyze

### 2. Data Provenance ✅
- Know which source provided which field
- Audit trail for data quality
- Can re-process if source data improves

### 3. Flexible Conflict Resolution ✅
- Priority-based (source quality)
- Recency-based (latest data wins)
- Field-specific strategies

### 4. Incremental Enrichment ✅
- Start with one source (PDL)
- Add more sources over time
- Each source enriches the master record

### 5. Search Layer Already Ready ✅
- Your generic search infrastructure works with unified Person
- Just need to update field mappings in YAML

---

## Example: Adding LinkedIn Data Source

### Step 1: Create LinkedIn Connector
```python
class LinkedInConnector(BaseConnector):
    connector_type = "linkedin"
    
    def read_stream(self, query: Dict) -> Iterator[Dict]:
        # Scrape or use LinkedIn API
        for profile in self._scrape_linkedin(query):
            yield profile
```

### Step 2: Create LinkedIn Transformer
```python
class LinkedInTransformer(BaseTransformer):
    def transform(self, records: List[Dict]) -> Dict:
        person_merge_service = PersonMergeService(self.db)
        
        for record in records:
            normalized = self._normalize_linkedin(record)
            
            person = person_merge_service.merge_person(
                source_name="linkedin",
                source_record_id=record['linkedin_id'],
                source_data=normalized,
                customer_id=self.customer_id
            )
```

### Step 3: That's It!
- Person record automatically merged
- Provenance tracked
- Search automatically updated
- No changes to search layer needed

---

## Migration Timeline

### Phase 1: Foundation (Week 1)
- [ ] Add `Person`, `PersonDataSource`, `PersonFieldProvenance` tables
- [ ] Create `PersonMergeService`
- [ ] Update tests

### Phase 2: PDL Integration (Week 2)
- [ ] Update PDLTransformer to create unified Person
- [ ] Migrate existing PDLPerson data
- [ ] Update search sync to use Person

### Phase 3: Second Source (Week 3-4)
- [ ] Add LinkedIn/Clearbit connector
- [ ] Create transformer
- [ ] Test conflict resolution
- [ ] Validate data quality

### Phase 4: Cleanup (Week 5)
- [ ] Deprecate PDLPerson table (optional)
- [ ] Update all queries to use Person
- [ ] Performance optimization
- [ ] Documentation

---

## Comparison: Before vs After

### Before (Current)
```
PDL API → PDLPerson (pdl_id)
          ↓
          Search (PDL data only)
```

**Limitations:**
- ❌ Can't add other sources
- ❌ No data merging
- ❌ Source-specific model

### After (Proposed)
```
PDL API → PersonMergeService → Person (person_id)
                                 ↓
LinkedIn API → PersonMergeService → Person (enriched)
                                     ↓
Clearbit API → PersonMergeService → Person (more enriched)
                                     ↓
                                   Search (best data)
```

**Benefits:**
- ✅ Multiple sources
- ✅ Data merging
- ✅ Unified model
- ✅ Provenance tracking
- ✅ Quality scoring

---

## Conclusion

### Your Infrastructure is 90% Ready! ✅

**What works perfectly:**
1. ✅ Search infrastructure (Elasticsearch, Neo4j) - **generic, reusable**
2. ✅ Staging layer (IngestedData) - **source-agnostic**
3. ✅ Transformer pattern - **easily extended**
4. ✅ Async sync pattern - **works for any Person source**

**What needs to be added:**
1. ⚠️ Unified `Person` model (instead of `PDLPerson`)
2. ⚠️ `PersonMergeService` for multi-source merging
3. ⚠️ Provenance tracking tables
4. ⚠️ Conflict resolution logic

**Effort Required:**
- New tables: 1 migration file
- PersonMergeService: ~300 lines
- Update PDLTransformer: ~50 lines
- Migration script: ~100 lines
- **Total: ~500 lines, 1-2 weeks**

### Recommended Next Steps

1. **Review this architecture** - Does it meet your needs?
2. **Prioritize sources** - What's the second data source? LinkedIn? Clearbit?
3. **Implement Phase 1** - Add Person tables (non-breaking)
4. **Build PersonMergeService** - Core merging logic
5. **Migrate PDL data** - Prove the pattern works
6. **Add second source** - Validate multi-source works

**You've built a solid foundation - extending to multiple sources is a natural evolution!** 🚀

