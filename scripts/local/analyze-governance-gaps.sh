#!/usr/bin/env bash
# Comprehensive governance gap analysis for AWS sandbox account
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "═══════════════════════════════════════════════════════════════"
echo "  Governance Gap Analysis - AWS Sandbox Account"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Prerequisites:"
echo "  ✓ AWS CLI configured with SSO"
echo "  ✓ uv package manager installed"
echo "  ✓ Governance package built"
echo ""
echo "This script will:"
echo "  1. Fetch all IAM principals with policy analysis"
echo "  2. Compute risk scores and ratings"
echo "  3. Identify orphan principals (missing Owner/Purpose)"
echo "  4. Generate actionable governance report"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""

cd "$PROJECT_ROOT"

# Run comprehensive analysis
uv run python << 'PYTHON_EOF'
import sys
sys.path.insert(0, 'packages/agentcore-governance/src')

from agentcore_governance import catalog, analyzer
from datetime import datetime
import json

print("Step 1: Fetching all IAM principals with policy analysis...")
print("-" * 70)
principals = catalog.fetch_principal_catalog()
print(f"✓ Fetched {len(principals)} principals\n")

print("Step 2: Enriching with risk scores...")
print("-" * 70)
principals = analyzer.enrich_principals_with_scores(principals)
principals = catalog.flag_inactive_principals(principals)
print(f"✓ Computed scores for {len(principals)} principals\n")

print("Step 3: Analyzing risk distribution...")
print("-" * 70)
risk_counts = {"LOW": 0, "MODERATE": 0, "HIGH": 0}
for p in principals:
    risk = p.get('risk_rating', 'UNKNOWN')
    risk_counts[risk] = risk_counts.get(risk, 0) + 1

total = len(principals)
print(f"  LOW:      {risk_counts['LOW']:3d} ({risk_counts['LOW']/total*100:5.1f}%)")
print(f"  MODERATE: {risk_counts['MODERATE']:3d} ({risk_counts['MODERATE']/total*100:5.1f}%)")
print(f"  HIGH:     {risk_counts['HIGH']:3d} ({risk_counts['HIGH']/total*100:5.1f}%)")
print()

print("Step 4: Detecting orphan principals...")
print("-" * 70)
orphans = analyzer.detect_orphan_principals(principals)
orphan_pct = len(orphans) / len(principals) * 100
print(f"  Orphans: {len(orphans):3d} ({orphan_pct:5.1f}%)")
print()

# Critical issues: High-risk orphans
high_risk = [p for p in principals if p.get('risk_rating') == 'HIGH']
high_risk_orphans = [p for p in high_risk if p in orphans]
inactive = [p for p in principals if p.get('inactive', False)]

print("═" * 70)
print("  GOVERNANCE GAP SUMMARY")
print("═" * 70)
print(f"  Total Principals:      {total:3d}")
print(f"  High-Risk:             {len(high_risk):3d}")
print(f"  Orphaned:              {len(orphans):3d}")
print(f"  Inactive (>30d):       {len(inactive):3d}")
print(f"  Critical (High+Orphan): {len(high_risk_orphans):3d}")
print()

if high_risk_orphans:
    print("CRITICAL ISSUES - High-Risk Orphaned Principals:")
    print("-" * 70)
    for i, p in enumerate(high_risk_orphans[:10], 1):
        name = p['id'].split('/')[-1]
        summary = p.get('policy_summary', {})
        score = p.get('least_privilege_score', 0)
        actions = summary.get('action_count', 0)
        wildcards = len(summary.get('wildcard_actions', []))

        print(f"{i}. {name}")
        print(f"   Score: {score:.1f}/100 | Actions: {actions} | Wildcards: {wildcards}")
        print(f"   Owner: {p.get('owner')} | Purpose: {p.get('purpose', 'N/A')[:50]}")
        print()

print("=" * 70)
print("RECOMMENDATIONS:")
print("=" * 70)
print("1. Tag all orphan principals with Owner and Purpose tags")
print("2. Review high-risk principals for least-privilege opportunities")
print("3. Remove or archive inactive principals (>30 days unused)")
print("4. Remediate critical issues (high-risk orphans) immediately")
print()

# Export detailed report
snapshot = catalog.export_catalog_snapshot(include_metadata=True)
report_file = f"governance-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
with open(report_file, 'w') as f:
    json.dump(snapshot, f, indent=2, default=str)

print(f"✓ Detailed report saved to: {report_file}")
print()

PYTHON_EOF

echo "═══════════════════════════════════════════════════════════════"
echo "  Analysis Complete"
echo "═══════════════════════════════════════════════════════════════"
