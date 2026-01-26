#!/bin/bash

# Script to verify Bedrock model access after quota restoration
# Usage: ./scripts/verify-bedrock-access.sh [region]

set -e

REGION="${1:-us-east-1}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=== Verifying Bedrock Model Access ==="
echo "Region: $REGION"
echo ""

# Test 1: List foundation models
echo -e "${BLUE}📋 Test 1: Listing foundation models...${NC}"
if aws bedrock list-foundation-models --region "$REGION" --query 'modelSummaries[?contains(modelId, `titan-embed`) || contains(modelId, `claude-haiku`)].{Model:modelId,Name:modelName}' --output table 2>/dev/null; then
    echo -e "${GREEN}✅ Bedrock API access confirmed${NC}"
else
    echo -e "${RED}❌ Cannot access Bedrock API${NC}"
    exit 1
fi
echo ""

# Test 2: Test Titan Embeddings V2
echo -e "${BLUE}🧪 Test 2: Testing Titan Embeddings V2...${NC}"
TITAN_MODEL="amazon.titan-embed-text-v2:0"
echo '{"inputText": "test query"}' > /tmp/titan-request.json

if aws bedrock-runtime invoke-model \
    --model-id "$TITAN_MODEL" \
    --cli-binary-format raw-in-base64-out \
    --body file:///tmp/titan-request.json \
    --region "$REGION" \
    /tmp/titan-response.json 2>/dev/null; then
    echo -e "${GREEN}✅ Titan Embeddings V2 accessible${NC}"
    EMBEDDING_SIZE=$(cat /tmp/titan-response.json | jq -r '.embedding | length' 2>/dev/null || echo "unknown")
    echo "   Embedding dimensions: $EMBEDDING_SIZE"
    rm -f /tmp/titan-response.json /tmp/titan-request.json
else
    ERROR=$(aws bedrock-runtime invoke-model \
        --model-id "$TITAN_MODEL" \
        --cli-binary-format raw-in-base64-out \
        --body file:///tmp/titan-request.json \
        --region "$REGION" \
        /tmp/titan-response.json 2>&1 || true)
    echo -e "${RED}❌ Titan Embeddings V2 not accessible${NC}"
    echo "   Error: $(echo "$ERROR" | grep -o 'Error.*' | head -1 || echo 'Unknown error')"
    rm -f /tmp/titan-request.json
fi
echo ""

# Test 3: Test Claude Haiku 4.5
echo -e "${BLUE}🧪 Test 3: Testing Claude Haiku 4.5...${NC}"
CLAUDE_MODEL="us.anthropic.claude-haiku-4-5-20251001-v1:0"
echo '{"anthropic_version": "bedrock-2023-05-31", "max_tokens": 100, "messages": [{"role": "user", "content": "Say hello"}]}' > /tmp/claude-request.json

if aws bedrock-runtime invoke-model \
    --model-id "$CLAUDE_MODEL" \
    --cli-binary-format raw-in-base64-out \
    --body file:///tmp/claude-request.json \
    --region "$REGION" \
    /tmp/claude-response.json 2>/dev/null; then
    echo -e "${GREEN}✅ Claude Haiku 4.5 accessible${NC}"
    RESPONSE=$(cat /tmp/claude-response.json | jq -r '.content[0].text' 2>/dev/null || echo "unknown")
    echo "   Response preview: ${RESPONSE:0:50}..."
    rm -f /tmp/claude-response.json /tmp/claude-request.json
else
    ERROR=$(aws bedrock-runtime invoke-model \
        --model-id "$CLAUDE_MODEL" \
        --cli-binary-format raw-in-base64-out \
        --body file:///tmp/claude-request.json \
        --region "$REGION" \
        /tmp/claude-response.json 2>&1 || true)
    echo -e "${RED}❌ Claude Haiku 4.5 not accessible${NC}"
    ERROR_MSG=$(echo "$ERROR" | grep -o 'Error.*' | head -1 || echo 'Unknown error')
    echo "   Error: $ERROR_MSG"
    rm -f /tmp/claude-request.json
    
    if echo "$ERROR_MSG" | grep -qi "access.*denied\|AccessDeniedException"; then
        echo ""
        echo -e "${YELLOW}⚠️  Anthropic models require use case submission (one-time per account):${NC}"
        echo ""
        echo -e "${BLUE}Option 1: Via Console Playground (Recommended)${NC}"
        echo "   1. Open: https://${REGION}.console.aws.amazon.com/bedrock/home?region=${REGION}"
        echo "   2. Click 'Model catalog' in the left menu"
        echo "   3. Search for 'Claude Haiku 4.5'"
        echo "   4. Click on the model, then click 'Open in Chat' or 'Open in Text'"
        echo "   5. The use case form will appear automatically"
        echo "   6. Fill out the form with your use case details and submit"
        echo "   7. Access is granted immediately after submission"
        echo ""
        echo -e "${BLUE}Option 2: Check if already submitted${NC}"
        echo "   Run: aws bedrock get-use-case-for-model-access --region ${REGION}"
        echo "   If you see a response, use case was already submitted"
        echo ""
        echo "   After submitting, re-run this script to verify access"
    fi
fi
echo ""

# Test 4: Check quotas (if service-quotas is available)
echo -e "${BLUE}📊 Test 4: Checking service quotas...${NC}"
if command -v aws &> /dev/null && aws service-quotas list-service-quotas --service-code bedrock --region "$REGION" &> /dev/null; then
    echo "Checking quotas for Claude Haiku 4.5..."
    aws service-quotas list-service-quotas \
        --service-code bedrock \
        --region "$REGION" \
        --query 'ServiceQuotas[?contains(QuotaName, `Haiku`) || contains(QuotaName, `Titan`)].{Name:QuotaName,Applied:Value,Default:DefaultValue}' \
        --output table 2>/dev/null || echo "   (Quota details may require additional permissions)"
else
    echo -e "${YELLOW}⚠️  Service Quotas API not accessible (this is optional)${NC}"
fi
echo ""

echo -e "${GREEN}=== Verification Complete ===${NC}"
echo ""
echo "If all tests passed, your Bedrock models are accessible!"
echo "You can now proceed with deployment:"
echo "  ./scripts/deploy.sh"
echo ""
