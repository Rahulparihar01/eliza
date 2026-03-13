"""
Unit tests for vector store index naming (OpenSearch Serverless alignment).

No AWS or OpenSearch required; tests normalization and _get_index_name only.
"""

import pytest
from src.services.rag.vector_store import VectorStore


class TestNormalizeIndexPrefix:
    """Test _normalize_index_prefix produces AOSS-safe prefix."""

    def test_empty_returns_rag_domains(self):
        assert VectorStore._normalize_index_prefix("") == "rag_domains"

    def test_lowercase(self):
        assert VectorStore._normalize_index_prefix("ELIZA_RAG_DEV") == "eliza_rag_dev"

    def test_invalid_chars_replaced_with_underscore(self):
        assert VectorStore._normalize_index_prefix("eliza rag") == "eliza_rag"
        assert VectorStore._normalize_index_prefix("a.b/c") == "a_b_c"

    def test_leading_hyphen_or_underscore_stripped(self):
        assert VectorStore._normalize_index_prefix("_prefix") == "prefix"
        assert VectorStore._normalize_index_prefix("-prefix") == "prefix"
        assert VectorStore._normalize_index_prefix("__x") == "x"

    def test_all_stripped_returns_rag(self):
        assert VectorStore._normalize_index_prefix("---") == "rag"
        assert VectorStore._normalize_index_prefix("___") == "rag"

    def test_max_length_255(self):
        long_prefix = "a" * 300
        result = VectorStore._normalize_index_prefix(long_prefix)
        assert len(result) == 255
        assert result == "a" * 255


class TestNormalizeIndexSuffix:
    """Test _normalize_index_suffix (domain_id) produces AOSS-safe suffix."""

    def test_empty_returns_default(self):
        assert VectorStore._normalize_index_suffix("") == "default"

    def test_lowercase(self):
        assert VectorStore._normalize_index_suffix("Domain-123") == "domain-123"

    def test_invalid_chars_replaced(self):
        assert VectorStore._normalize_index_suffix("domain.id/here") == "domain_id_here"

    def test_leading_hyphen_underscore_stripped(self):
        assert VectorStore._normalize_index_suffix("_domain") == "domain"
        assert VectorStore._normalize_index_suffix("-domain") == "domain"

    def test_numeric_domain_id(self):
        assert VectorStore._normalize_index_suffix("12345") == "12345"

    def test_max_length_255(self):
        long_domain = "d" * 300
        result = VectorStore._normalize_index_suffix(long_domain)
        assert len(result) == 255


class TestGetIndexName:
    """Test full index name: prefix + suffix, AOSS-safe, max 255."""

    def test_default_prefix_and_domain(self):
        store = VectorStore(index_prefix="rag_domains", use_local=True)
        assert store._get_index_name("kb-1") == "rag_domains_kb-1"

    def test_custom_prefix_from_terraform_style(self):
        store = VectorStore(index_prefix="eliza_rag_dev", use_local=True)
        assert store._get_index_name("domain-1") == "eliza_rag_dev_domain-1"

    def test_prefix_normalized_on_init(self):
        store = VectorStore(index_prefix="  ELIZA_RAG  ", use_local=True)
        assert store.index_prefix == "eliza_rag"
        assert store._get_index_name("d1") == "eliza_rag_d1"

    def test_full_name_capped_at_255(self):
        store = VectorStore(index_prefix="p" * 100, use_local=True)
        suffix = "s" * 200
        name = store._get_index_name(suffix)
        assert len(name) == 255
        assert name.startswith("p" * 100 + "_")
