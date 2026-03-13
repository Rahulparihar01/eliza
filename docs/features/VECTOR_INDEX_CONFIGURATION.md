# Vector Index Configuration Guide

## ✅ Configuration Verified

All components now use centralized configuration for the FAISS vector index.

---

## 📋 Configuration Architecture

### Centralized Settings (`src/core/config.py`)

```python
class Settings(BaseSettings):
    # Vector storage configuration
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    faiss_index_type: str = "IndexFlatIP"
    vector_index_directory: str = "./data/vectors"  # ← Single source of truth
```

### Configuration Chain

```
config.py (Settings)
    ↓ vector_index_directory
VectorService (__init__)
    ↓ self.settings.vector_index_directory
DocumentSearchTool (CrewAI)
    ↓ _vector_service.vector_dir
FAISS Index Files
    ↓ data/vectors/faiss_index.bin
    ↓ data/vectors/chunk_mapping.json
```

---

## 🔧 Environment Variables

You can override the default configuration using environment variables:

### Vector Index Location
```bash
# Change the vector index directory
export VECTOR_INDEX_DIRECTORY="/custom/path/to/vectors"
```

### Embedding Model
```bash
# Use a different embedding model
export EMBEDDING_MODEL="sentence-transformers/all-mpnet-base-v2"
export EMBEDDING_DIMENSION=768  # Must match model dimension
```

### FAISS Index Type
```bash
# Change FAISS index type (IndexFlatIP, IndexFlatL2, IndexIVFFlat, etc.)
export FAISS_INDEX_TYPE="IndexFlatL2"
```

### Docker Compose Example

```yaml
# docker-compose.yml
services:
  app:
    environment:
      - VECTOR_INDEX_DIRECTORY=/app/data/vectors
      - EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
      - EMBEDDING_DIMENSION=384
    volumes:
      - app_vectors:/app/data/vectors  # Persistent storage

volumes:
  app_vectors:
```

---

## 📊 Current Configuration

### Default Values
- **Vector Index Directory**: `./data/vectors`
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Embedding Dimension**: `384`
- **FAISS Index Type**: `IndexFlatIP` (Inner Product / Cosine Similarity)

### File Locations (Inside Container)
```
/app/
├── data/
│   └── vectors/
│       ├── faiss_index.bin      ← Binary FAISS index
│       └── chunk_mapping.json   ← Position → chunk_id mapping
```

### File Locations (Host - Docker Volume)
```
docker volume inspect docker_app_data

# Typically maps to:
/var/lib/docker/volumes/docker_app_data/_data/vectors/
├── faiss_index.bin
└── chunk_mapping.json
```

---

## 🧪 Verification

### Run Configuration Test

```bash
# Inside container
docker exec docker-app-1 python test_vector_index_config.py

# Expected output:
# 🎉 SUCCESS! All components correctly reference the centralized configuration.
```

### Check Current Status

```python
from src.core.config import get_settings
from src.services.vector_service import VectorService

settings = get_settings()
print(f"Vector Index Directory: {settings.vector_index_directory}")

vs = VectorService()
stats = await vs.get_index_stats()
print(f"Total Vectors: {stats['total_vectors']}")
```

### Manual Verification

```bash
# Check if index exists
docker exec docker-app-1 ls -lh data/vectors/

# Expected:
# faiss_index.bin
# chunk_mapping.json

# Check index stats
docker exec docker-app-1 python -c "
from src.services.vector_service import VectorService
import asyncio
vs = VectorService()
stats = asyncio.run(vs.get_index_stats())
print(f'Total vectors: {stats[\"total_vectors\"]}')
print(f'Index file: {vs.index_file}')
"
```

---

## 🔄 How Components Use Configuration

### 1. VectorService (Core Service)

```python
class VectorService(BaseService):
    def __init__(self):
        self.settings = get_settings()
        
        # Uses centralized config
        self.embedding_model_name = self.settings.embedding_model
        self.embedding_dimension = self.settings.embedding_dimension
        self.vector_dir = Path(self.settings.vector_index_directory)
        
        # Index files
        self.index_file = self.vector_dir / "faiss_index.bin"
        self.mapping_file = self.vector_dir / "chunk_mapping.json"
```

**Usage**: Automatically used during document processing

### 2. DocumentSearchTool (CrewAI Tool)

```python
class DocumentSearchTool(BaseTool):
    def __init__(self, customer_id: str, **kwargs):
        super().__init__(customer_id=customer_id, **kwargs)
        
        # Creates VectorService (which uses config)
        self._vector_service = VectorService()
```

**Usage**: Used by CrewAI agents for semantic search

### 3. Document Processor (Processing Pipeline)

```python
class DocumentProcessor(BaseService):
    def __init__(self):
        # VectorService automatically configured
        self.vector_service = VectorService()
    
    async def process_document_sync(self, document_id: int):
        # ... extract, chunk ...
        
        # Generate embeddings and update FAISS index
        self._generate_embeddings_sync(document_id, db)
```

**Usage**: Automatically populates FAISS index during upload

---

## 🚀 Migration Guide

### Changing Vector Index Location

If you need to move the vector index to a different location:

**Step 1: Update Configuration**
```bash
# Set new location
export VECTOR_INDEX_DIRECTORY="/new/path/to/vectors"
```

**Step 2: Copy Existing Index (Optional)**
```bash
# Copy existing index to new location
docker exec docker-app-1 cp -r data/vectors /new/path/to/vectors
```

**Step 3: Rebuild Index (Alternative)**
```python
from src.services.vector_service import VectorService
import asyncio

vs = VectorService()
result = asyncio.run(vs.rebuild_index(customer_id='eliza'))
print(result)  # Should create index in new location
```

**Step 4: Restart Application**
```bash
docker-compose restart app
```

### Using Different Embedding Model

**Warning**: Changing embedding models requires rebuilding the entire index!

**Step 1: Update Configuration**
```bash
export EMBEDDING_MODEL="sentence-transformers/all-mpnet-base-v2"
export EMBEDDING_DIMENSION=768  # Must match model dimension
```

**Step 2: Clear Old Index**
```bash
docker exec docker-app-1 rm -rf data/vectors/*
```

**Step 3: Rebuild Index**
```python
from src.services.vector_service import VectorService
import asyncio

vs = VectorService()
result = asyncio.run(vs.rebuild_index(customer_id='eliza'))
```

**Step 4: Verify**
```python
stats = asyncio.run(vs.get_index_stats())
assert stats['embedding_model'] == "sentence-transformers/all-mpnet-base-v2"
assert stats['embedding_dimension'] == 768
```

---

## 🛠️ Troubleshooting

### Issue: Tool Not Finding Index

**Symptom**: DocumentSearchTool returns "FAISS index is empty"

**Check**:
```bash
docker exec docker-app-1 python test_vector_index_config.py
```

**Solution**:
1. Verify index files exist: `docker exec docker-app-1 ls data/vectors/`
2. Check permissions: Index files should be readable
3. Rebuild index if needed: Use `rebuild_index()` API endpoint

### Issue: Different Components Using Different Paths

**Symptom**: Configuration test shows ❌ FAIL

**Solution**:
1. Ensure all files are updated (config.py, vector_service.py)
2. Restart container: `docker-compose restart app`
3. Re-run test: `docker exec docker-app-1 python test_vector_index_config.py`

### Issue: Index Not Persisting

**Symptom**: Index disappears after container restart

**Solution**:
```yaml
# Ensure volume is mounted in docker-compose.yml
services:
  app:
    volumes:
      - app_data:/app/data  # ← Must include this

volumes:
  app_data:  # ← Must define volume
```

---

## 📈 Performance Considerations

### Index Type Selection

**IndexFlatIP** (Current Default)
- ✅ Exact search (100% accuracy)
- ✅ Best for < 100K vectors
- ✅ Fast for small datasets
- ✅ No training required
- ❌ Slower for > 1M vectors

**IndexFlatL2**
- Similar to IndexFlatIP but uses L2 distance
- Good for Euclidean distance metrics

**IndexIVFFlat** (Recommended for > 100K vectors)
- ✅ Fast approximate search
- ✅ Good for > 100K vectors
- ✅ Configurable accuracy/speed tradeoff
- ❌ Requires training on sample data

**IndexHNSW** (Best for production)
- ✅ State-of-the-art approximate search
- ✅ Excellent for > 1M vectors
- ✅ Very fast queries
- ❌ More memory usage
- ❌ Slower index building

### Changing Index Type

```bash
# Update config
export FAISS_INDEX_TYPE="IndexHNSW"

# Rebuild index
docker exec docker-app-1 python -c "
from src.services.vector_service import VectorService
import asyncio
vs = VectorService()
asyncio.run(vs.rebuild_index(customer_id='eliza'))
"
```

---

## ✅ Summary

### What We Achieved

1. **✅ Centralized Configuration**
   - Single source of truth in `config.py`
   - All components reference same settings
   - Easy to override via environment variables

2. **✅ Verified Configuration**
   - Test script confirms all components aligned
   - 5 configuration checks all passing
   - Clear configuration chain

3. **✅ Production Ready**
   - Proper path management
   - Docker volume support
   - Environment variable overrides
   - Migration guide included

### Configuration Flow

```
Environment Variable (VECTOR_INDEX_DIRECTORY)
    ↓ (if set, overrides default)
config.py (Settings.vector_index_directory = "./data/vectors")
    ↓ (imported by)
VectorService (self.settings.vector_index_directory)
    ↓ (creates)
FAISS Index Files (faiss_index.bin, chunk_mapping.json)
    ↓ (used by)
DocumentSearchTool → CrewAI Agents → Semantic Search
```

**All components are properly configured and verified! ✨**

