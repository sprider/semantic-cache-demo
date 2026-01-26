#!/bin/bash

echo "=== AWS Bedrock Quota Increase Request Guide ==="
echo ""
echo "If you're experiencing frequent throttling, you may need to request quota increases."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📋 Current Bedrock Quotas (Default for new accounts):${NC}"
echo ""
echo "   Model: Claude Haiku 4.5"
echo "   - Requests per minute: 4,000 (new accounts may have lower limits)"
echo "   - Tokens per minute: 300,000 (new accounts may have lower limits)"
echo ""
echo "   Model: Titan Embeddings V2"
echo "   - Requests per minute: 4,000"
echo "   - Tokens per minute: 300,000"
echo ""

echo -e "${YELLOW}⚠️  New AWS accounts often have significantly reduced quotas:${NC}"
echo "   - As low as 4,000 tokens/minute total across all models"
echo "   - This can cause immediate throttling even with light usage"
echo ""

echo -e "${GREEN}🔧 How to Request Quota Increases:${NC}"
echo ""
echo "1. Open AWS Management Console"
echo "2. Navigate to Service Quotas service"
echo "3. Search for 'Amazon Bedrock'"
echo "4. Find the specific quota you need to increase:"
echo "   - 'Anthropic Claude Haiku 4.5 requests per minute'"
echo "   - 'Anthropic Claude Haiku 4.5 tokens per minute'"
echo "   - 'Amazon Titan Text Embeddings V2 requests per minute'"
echo "   - 'Amazon Titan Text Embeddings V2 tokens per minute'"
echo "5. Click 'Request quota increase'"
echo "6. Specify your desired limit (e.g., 10,000 requests/minute)"
echo "7. Provide business justification"
echo ""

echo -e "${BLUE}📝 Sample Business Justification:${NC}"
echo ""
echo "\"We are developing a semantic caching solution for our application"
echo "that requires reliable access to Bedrock models. Our use case involves"
echo "processing user queries through embeddings and LLM responses."
echo "We expect [X] requests per minute during peak usage and need"
echo "increased quotas to ensure consistent performance for our users.\""
echo ""

echo -e "${GREEN}⏱️  Processing Time:${NC}"
echo "   - Most quota increase requests are processed within 24-48 hours"
echo "   - Some may require additional review and take longer"
echo ""

echo -e "${YELLOW}💡 Alternative Solutions While Waiting:${NC}"
echo ""
echo "1. Use different AWS regions (quotas are per-region)"
echo "2. Implement request queuing in your application"
echo "3. Use multiple AWS accounts for higher aggregate limits"
echo "4. Reduce request frequency with longer delays"
echo ""

echo -e "${BLUE}🌍 Regions with Better Availability:${NC}"
echo "   - us-west-2 (Oregon)"
echo "   - eu-west-1 (Ireland)"
echo "   - ap-southeast-2 (Sydney)"
echo ""

echo -e "${GREEN}✅ Quick Commands to Check Current Usage:${NC}"
echo ""
echo "# Check current quotas"
echo "aws service-quotas get-service-quota --service-code bedrock --quota-code L-12345678"
echo ""
echo "# List all Bedrock quotas"
echo "aws service-quotas list-service-quotas --service-code bedrock"
echo ""

echo -e "${RED}🚨 Important Notes:${NC}"
echo ""
echo "- Quota increases are per AWS region"
echo "- You need to request increases for each model separately"
echo "- Higher quotas may incur higher costs"
echo "- Monitor your usage to avoid unexpected charges"
echo ""

echo "=== End of Guide ==="