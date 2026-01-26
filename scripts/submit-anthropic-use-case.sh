#!/bin/bash

# Script to guide users through submitting Anthropic use case details
# Note: The Model Access page is retired, but Anthropic models still require
# a one-time use case submission via the console playground

set -e

REGION="${1:-us-east-1}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=== Anthropic Claude Model Access - Use Case Submission ==="
echo ""
echo "According to AWS documentation (2025):"
echo "- Model Access page has been retired"
echo "- Serverless foundation models auto-enable on first invocation"
echo "- Anthropic models require a one-time use case submission"
echo ""

# Check if already submitted
echo -e "${BLUE}Checking if use case was already submitted...${NC}"
if aws bedrock get-use-case-for-model-access --region "$REGION" 2>/dev/null; then
    echo -e "${GREEN}✅ Use case details already submitted for this account${NC}"
    echo ""
    echo "You should be able to invoke Claude models now."
    echo "Test with: ./scripts/verify-bedrock-access.sh $REGION"
    exit 0
else
    echo -e "${YELLOW}⚠️  Use case details not yet submitted${NC}"
    echo ""
fi

echo -e "${BLUE}📝 How to Submit Use Case Details:${NC}"
echo ""
echo "The easiest way is through the Bedrock Console Playground:"
echo ""
echo "1. Open the Bedrock Console:"
echo "   https://${REGION}.console.aws.amazon.com/bedrock/home?region=${REGION}"
echo ""
echo "2. Click 'Model catalog' in the left navigation menu"
echo ""
echo "3. Search for 'Claude Haiku 4.5' or 'Claude'"
echo ""
echo "4. Click on 'Anthropic Claude Haiku 4.5'"
echo ""
echo "5. Click 'Open in Chat' or 'Open in Text' button"
echo ""
echo "6. A use case form will appear automatically"
echo "   - Fill out your use case details"
echo "   - Describe how you plan to use the model"
echo "   - Submit the form"
echo ""
echo "7. Access is granted immediately after successful submission"
echo ""
echo "8. Verify access by running:"
echo "   ./scripts/verify-bedrock-access.sh $REGION"
echo ""
echo -e "${YELLOW}Note:${NC} This is a one-time requirement per AWS account."
echo "Once submitted, all users in the account can access Anthropic models"
echo "(subject to IAM policies)."
echo ""
