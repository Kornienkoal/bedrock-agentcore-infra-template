"""Unit tests for analyzer scoring logic."""

from agentcore_governance import analyzer


class TestComputeLeastPrivilegeScore:
    """Tests for compute_least_privilege_score."""

    def test_perfect_score(self):
        """Test policy with perfect least-privilege score."""
        policies = [
            {
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "s3:GetObject",
                        "Resource": "arn:aws:s3:::specific-bucket/specific-key",
                    }
                ]
            }
        ]

        score = analyzer.compute_least_privilege_score(policies)
        assert score > 95.0  # High score for narrow policy

    def test_wildcard_actions_penalty(self):
        """Test penalty for wildcard actions."""
        policies = [
            {
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:*", "dynamodb:*"],
                        "Resource": "arn:aws:s3:::bucket/*",
                    }
                ]
            }
        ]

        score = analyzer.compute_least_privilege_score(policies)
        assert score < 95.0  # Penalty for wildcards

    def test_wildcard_resource_penalty(self):
        """Test penalty for wildcard resources."""
        policies = [
            {
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "s3:GetObject",
                        "Resource": "*",
                    }
                ]
            }
        ]

        score = analyzer.compute_least_privilege_score(policies)
        assert score < 95.0  # Penalty for wildcard resource

    def test_empty_policy(self):
        """Test scoring with empty policy."""
        score = analyzer.compute_least_privilege_score([])
        assert score == 100.0  # No policy = perfect score


class TestDetectOrphanPrincipals:
    """Tests for detect_orphan_principals."""

    def test_orphan_missing_owner(self):
        """Test detection of principal with missing owner."""
        principals = [
            {"id": "role-1", "owner": "unknown", "purpose": "Test role"},
            {"id": "role-2", "owner": "team-a", "purpose": "Production role"},
        ]

        orphans = analyzer.detect_orphan_principals(principals)

        assert len(orphans) == 1
        assert orphans[0]["id"] == "role-1"

    def test_orphan_missing_purpose(self):
        """Test detection of principal with missing purpose."""
        principals = [
            {"id": "role-1", "owner": "team-a", "purpose": ""},
            {"id": "role-2", "owner": "team-b", "purpose": "Valid purpose"},
        ]

        orphans = analyzer.detect_orphan_principals(principals)

        assert len(orphans) == 1
        assert orphans[0]["id"] == "role-1"

    def test_no_orphans(self):
        """Test when all principals have proper metadata."""
        principals = [
            {"id": "role-1", "owner": "team-a", "purpose": "Production"},
            {"id": "role-2", "owner": "team-b", "purpose": "Development"},
        ]

        orphans = analyzer.detect_orphan_principals(principals)

        assert len(orphans) == 0


class TestComputeRiskRating:
    """Tests for compute_risk_rating."""

    def test_low_risk(self):
        """Test low risk rating."""
        principal = {
            "policy_summary": {
                "wildcard_actions": [],
                "resource_scope_wideness": "NARROW",
                "action_count": 10,
            },
            "inactive": False,
            "least_privilege_score": 95.0,
        }

        rating = analyzer.compute_risk_rating(principal)
        assert rating == "LOW"

    def test_high_risk(self):
        """Test high risk rating."""
        principal = {
            "policy_summary": {
                "wildcard_actions": ["s3:*", "dynamodb:*", "iam:*", "ec2:*", "lambda:*", "rds:*"],
                "resource_scope_wideness": "BROAD",
                "action_count": 150,
            },
            "inactive": True,
            "least_privilege_score": 30.0,
        }

        rating = analyzer.compute_risk_rating(principal)
        assert rating == "HIGH"

    def test_moderate_risk(self):
        """Test moderate risk rating."""
        principal = {
            "policy_summary": {
                "wildcard_actions": ["s3:*"],
                "resource_scope_wideness": "MODERATE",
                "action_count": 60,
            },
            "inactive": False,
            "least_privilege_score": 70.0,
        }

        rating = analyzer.compute_risk_rating(principal)
        assert rating == "MODERATE"
