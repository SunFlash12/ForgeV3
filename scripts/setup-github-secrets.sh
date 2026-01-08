#!/bin/bash
# Forge V3 - GitHub Secrets Setup Script
#
# This script sets up the required GitHub secrets for CI/CD.
# Requires: GitHub CLI (gh) authenticated with your account
#
# Usage:
#   ./scripts/setup-github-secrets.sh
#
# Or set secrets manually at:
#   https://github.com/SunFlash12/ForgeV3/settings/secrets/actions

set -e

echo "============================================================"
echo "Forge V3 - GitHub Secrets Setup"
echo "============================================================"
echo ""

# Check if gh is installed
if ! command -v gh &> /dev/null; then
    echo "GitHub CLI (gh) is not installed."
    echo ""
    echo "Install it from: https://cli.github.com/"
    echo ""
    echo "Or set secrets manually at:"
    echo "  https://github.com/SunFlash12/ForgeV3/settings/secrets/actions"
    echo ""
    echo "Required secrets:"
    echo "  - NEO4J_URI"
    echo "  - NEO4J_USERNAME"
    echo "  - NEO4J_PASSWORD"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "Please authenticate with GitHub first:"
    echo "  gh auth login"
    exit 1
fi

echo "Enter your Neo4j credentials:"
echo ""

# Get Neo4j URI
read -p "NEO4J_URI (e.g., neo4j+s://xxx.databases.neo4j.io): " NEO4J_URI
if [ -z "$NEO4J_URI" ]; then
    echo "Error: NEO4J_URI is required"
    exit 1
fi

# Get Neo4j Username
read -p "NEO4J_USERNAME [neo4j]: " NEO4J_USERNAME
NEO4J_USERNAME=${NEO4J_USERNAME:-neo4j}

# Get Neo4j Password
read -s -p "NEO4J_PASSWORD: " NEO4J_PASSWORD
echo ""
if [ -z "$NEO4J_PASSWORD" ]; then
    echo "Error: NEO4J_PASSWORD is required"
    exit 1
fi

echo ""
echo "Setting GitHub secrets..."
echo ""

# Set secrets
gh secret set NEO4J_URI --body "$NEO4J_URI"
echo "  ✓ NEO4J_URI set"

gh secret set NEO4J_USERNAME --body "$NEO4J_USERNAME"
echo "  ✓ NEO4J_USERNAME set"

gh secret set NEO4J_PASSWORD --body "$NEO4J_PASSWORD"
echo "  ✓ NEO4J_PASSWORD set"

echo ""
echo "============================================================"
echo "All secrets configured successfully!"
echo "============================================================"
echo ""
echo "Your CI/CD pipeline is now ready to use."
echo "Push to master or create a PR to trigger the workflow."
