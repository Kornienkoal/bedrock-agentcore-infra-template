"""Unit tests for integrity hash utility."""

from agentcore_governance import integrity


class TestComputeIntegrityHash:
    """Tests for compute_integrity_hash."""

    def test_deterministic_hash(self):
        """Test that same inputs produce same hash."""
        fields = ["field1", "field2", "field3"]

        hash1 = integrity.compute_integrity_hash(fields)
        hash2 = integrity.compute_integrity_hash(fields)

        assert hash1 == hash2

    def test_different_inputs_different_hash(self):
        """Test that different inputs produce different hashes."""
        fields1 = ["field1", "field2"]
        fields2 = ["field1", "field3"]

        hash1 = integrity.compute_integrity_hash(fields1)
        hash2 = integrity.compute_integrity_hash(fields2)

        assert hash1 != hash2

    def test_order_matters(self):
        """Test that field order affects hash."""
        fields1 = ["a", "b", "c"]
        fields2 = ["c", "b", "a"]

        hash1 = integrity.compute_integrity_hash(fields1)
        hash2 = integrity.compute_integrity_hash(fields2)

        assert hash1 != hash2

    def test_empty_fields(self):
        """Test hashing empty field list."""
        fields = []

        hash_result = integrity.compute_integrity_hash(fields)

        assert hash_result  # Should return a valid hash
        assert len(hash_result) == 64  # SHA256 hex digest length

    def test_special_characters(self):
        """Test hashing fields with special characters."""
        fields = ["field|with|pipes", "field;with;semicolons", "field\\nwith\\nnewlines"]

        hash_result = integrity.compute_integrity_hash(fields)

        assert hash_result
        assert len(hash_result) == 64

    def test_unicode_characters(self):
        """Test hashing fields with unicode characters."""
        fields = ["field_α", "field_β", "field_日本語"]

        hash_result = integrity.compute_integrity_hash(fields)

        assert hash_result
        assert len(hash_result) == 64

    def test_reproducible_across_calls(self):
        """Test that hash is reproducible across multiple calls."""
        fields = ["event_id", "timestamp", "correlation_id"]

        hashes = [integrity.compute_integrity_hash(fields) for _ in range(10)]

        assert all(h == hashes[0] for h in hashes)
