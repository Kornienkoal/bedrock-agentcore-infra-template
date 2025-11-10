"""Integration test for ABAC matrix exporter."""

import csv
import io

from agentcore_governance import abac_matrix


class TestExportABACMatrix:
    """Integration tests for ABAC matrix export."""

    def test_export_with_sample_attributes(self):
        """Test exporting ABAC matrix with sample attributes."""
        attributes = [
            {
                "attribute": "environment",
                "source": "tags",
                "potential_use": "Environment-based policies",
                "collection_method": "IAM tag listing",
            },
            {
                "attribute": "risk_rating",
                "source": "analyzer",
                "potential_use": "Risk-based access control",
                "collection_method": "Computed score",
            },
        ]

        result = abac_matrix.export_abac_matrix(attributes)

        assert "attributes" in result
        assert "csv_export" in result
        assert len(result["attributes"]) == 2
        assert result["attributes"][0]["attribute"] == "environment"

    def test_csv_export_format(self):
        """Test CSV export format correctness."""
        attributes = [
            {
                "attribute": "owner",
                "source": "IAM tags",
                "potential_use": "Ownership enforcement",
                "collection_method": "Tag API",
            },
        ]

        result = abac_matrix.export_abac_matrix(attributes)
        csv_content = result["csv_export"]

        # Parse CSV to validate
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["attribute"] == "owner"
        assert rows[0]["source"] == "IAM tags"

    def test_export_empty_attributes(self):
        """Test exporting empty attribute list."""
        result = abac_matrix.export_abac_matrix([])

        assert result["attributes"] == []
        assert result["csv_export"] == ""


class TestGenerateDefaultABACMatrix:
    """Integration tests for default ABAC matrix generation."""

    def test_generate_default_matrix(self):
        """Test generating default ABAC matrix."""
        result = abac_matrix.generate_default_abac_matrix()

        assert "attributes" in result
        assert len(result["attributes"]) >= 5  # Should have at least 5 default attributes

        # Check for key attributes
        attr_names = [a["attribute"] for a in result["attributes"]]
        assert "environment" in attr_names
        assert "sensitivity_level" in attr_names
        assert "owner" in attr_names
        assert "risk_rating" in attr_names
        assert "last_used_at" in attr_names

    def test_default_matrix_has_csv_export(self):
        """Test that default matrix includes CSV export."""
        result = abac_matrix.generate_default_abac_matrix()

        assert "csv_export" in result
        assert result["csv_export"]  # Should not be empty

        # Validate CSV format
        lines = result["csv_export"].strip().split("\n")
        assert len(lines) > 1  # Header + at least one data row
        assert "attribute,source,potential_use,collection_method" in lines[0]

    def test_default_matrix_attribute_completeness(self):
        """Test that all default attributes have required fields."""
        result = abac_matrix.generate_default_abac_matrix()

        for attr in result["attributes"]:
            assert "attribute" in attr
            assert "source" in attr
            assert "potential_use" in attr
            assert "collection_method" in attr
            # All fields should be non-empty
            assert attr["attribute"]
            assert attr["source"]
            assert attr["potential_use"]
            assert attr["collection_method"]
