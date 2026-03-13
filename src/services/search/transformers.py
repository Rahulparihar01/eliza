"""
Field transformers for search sync services.

Provides reusable transformation logic for converting source data
to search engine formats.
"""
from typing import Dict, Any, List
from abc import ABC, abstractmethod


class BaseTransformer(ABC):
    """Base class for field transformers."""
    
    @abstractmethod
    def transform(
        self,
        document: Dict[str, Any],
        source_data: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform document fields.
        
        Args:
            document: Current document being built
            source_data: Original source data
            config: Transformer configuration
            
        Returns:
            Updated document
        """
        pass


class FlattenNestedFieldsTransformer(BaseTransformer):
    """Flatten nested JSON arrays into searchable strings."""
    
    def transform(
        self,
        document: Dict[str, Any],
        source_data: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Flatten specified nested fields."""
        fields_to_flatten = config.get('apply_to', [])
        
        for field in fields_to_flatten:
            if field in source_data:
                nested_data = source_data[field]
                
                if isinstance(nested_data, list):
                    # Extract text from array of objects
                    flattened = []
                    for item in nested_data:
                        if isinstance(item, dict):
                            # Extract all string values
                            flattened.extend([
                                str(v) for v in item.values()
                                if isinstance(v, (str, int, float))
                            ])
                        else:
                            flattened.append(str(item))
                    
                    document[f"{field}_text"] = " ".join(flattened)
        
        return document


class ExtractKeywordsTransformer(BaseTransformer):
    """Extract keywords from text fields."""
    
    def transform(
        self,
        document: Dict[str, Any],
        source_data: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract keywords from specified fields."""
        fields = config.get('apply_to', [])
        
        for field in fields:
            if field in document and isinstance(document[field], (str, list)):
                if isinstance(document[field], list):
                    # Already keywords
                    continue
                    
                # Simple keyword extraction (can be enhanced with NLP)
                text = document[field]
                keywords = [
                    word.strip().lower()
                    for word in text.split()
                    if len(word.strip()) > 2
                ]
                document[f"{field}_keywords"] = list(set(keywords))
        
        return document


class GenerateEmbeddingsTransformer(BaseTransformer):
    """Generate vector embeddings for semantic search."""
    
    def transform(
        self,
        document: Dict[str, Any],
        source_data: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate embeddings from specified fields."""
        # Placeholder for embedding generation
        # In production, would use sentence-transformers or similar
        
        fields = config.get('apply_to', [])
        output_field = config.get('output_field', 'search_vector')
        
        # Combine text from specified fields
        text_parts = []
        for field in fields:
            if field in document and document[field]:
                text_parts.append(str(document[field]))
        
        combined_text = " ".join(text_parts)
        
        # Placeholder: In production, generate real embeddings
        # document[output_field] = generate_embedding(combined_text)
        
        # For now, just store the text for future embedding
        document[f"{output_field}_text"] = combined_text
        
        return document


# Registry of available transformers
TRANSFORMER_REGISTRY = {
    'flatten_nested_fields': FlattenNestedFieldsTransformer(),
    'extract_keywords': ExtractKeywordsTransformer(),
    'generate_embeddings': GenerateEmbeddingsTransformer(),
}


def get_transformer(name: str) -> BaseTransformer:
    """Get transformer by name."""
    return TRANSFORMER_REGISTRY.get(name)

