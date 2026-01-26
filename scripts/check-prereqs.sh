#!/bin/bash
set -e

echo "=== Semantic Cache Demo - Prerequisites Check ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Function to check command exists
check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "✅ $1 is installed"
    else
        echo -e "${RED}❌ $1 is not installed${NC}"
        ERRORS=$((ERRORS + 1))
    fi
}

# Function to check AWS CLI version
check_aws_version() {
    if command -v aws &> /dev/null; then
        VERSION=$(aws --version 2>&1 | cut -d/ -f2 | cut -d' ' -f1)
        MAJOR=$(echo $VERSION | cut -d. -f1)
        if [ "$MAJOR" -ge 2 ]; then
            echo -e "✅ AWS CLI v$VERSION (>= 2.0 required)"
        else
            echo -e "${RED}❌ AWS CLI v$VERSION is too old (>= 2.0 required)${NC}"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo -e "${RED}❌ AWS CLI is not installed${NC}"
        ERRORS=$((ERRORS + 1))
    fi
}

# Function to check SAM CLI version
check_sam_version() {
    if command -v sam &> /dev/null; then
        VERSION=$(sam --version 2>&1 | cut -d' ' -f4)
        echo -e "✅ SAM CLI v$VERSION"
    else
        echo -e "${RED}❌ SAM CLI is not installed${NC}"
        ERRORS=$((ERRORS + 1))
    fi
}

# Function to check AWS credentials
check_aws_credentials() {
    if aws sts get-caller-identity &> /dev/null; then
        ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
        REGION=$(aws configure get region)
        echo -e "✅ AWS credentials configured"
        echo -e "   Account: $ACCOUNT"
        echo -e "   Region: ${REGION:-us-east-1 (default)}"
    else
        echo -e "${RED}❌ AWS credentials not configured${NC}"
        echo -e "   Run: aws configure"
        ERRORS=$((ERRORS + 1))
    fi
}

# Function to check region support
check_region_support() {
    REGION=$(aws configure get region)
    REGION=${REGION:-us-east-1}
    
    case $REGION in
        us-east-1|us-east-2|us-west-2|eu-west-1|ap-northeast-1)
            echo -e "✅ Region $REGION supports S3 Vectors and Bedrock"
            ;;
        *)
            echo -e "${YELLOW}⚠️  Region $REGION may not support S3 Vectors${NC}"
            echo -e "   Recommended regions: us-east-1, us-east-2, us-west-2, eu-west-1, ap-northeast-1"
            ;;
    esac
}

# Function to check Bedrock model access
check_bedrock_models() {
    echo ""
    echo "🤖 Checking Bedrock model access..."
    echo -e "${YELLOW}Note: Models now auto-enable on first use (no manual activation required)${NC}"
    
    # Try to list foundation models to verify Bedrock access
    if aws bedrock list-foundation-models --region us-east-1 &> /dev/null; then
        echo -e "✅ Bedrock API access confirmed"
        echo -e "   Models will auto-enable when first invoked"
    else
        echo -e "${RED}❌ Cannot access Bedrock API${NC}"
        echo -e "   Check IAM permissions for bedrock:ListFoundationModels"
        ERRORS=$((ERRORS + 1))
    fi
}

# Function to check Python version
check_python() {
    if command -v python3 &> /dev/null; then
        VERSION=$(python3 --version | cut -d' ' -f2)
        MAJOR=$(echo $VERSION | cut -d. -f1)
        MINOR=$(echo $VERSION | cut -d. -f2)
        
        if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 11 ]; then
            echo -e "✅ Python $VERSION (>= 3.11 required)"
        else
            echo -e "${RED}❌ Python $VERSION is too old (>= 3.11 required)${NC}"
            echo -e "   Lambda runtime uses Python 3.11"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo -e "${RED}❌ Python 3 not found${NC}"
        echo -e "   Install Python 3.11+ for compatibility with Lambda runtime"
        ERRORS=$((ERRORS + 1))
    fi
}

# Function to check pip3
check_pip3() {
    if command -v pip3 &> /dev/null; then
        echo -e "✅ pip3 is installed"
    else
        echo -e "${YELLOW}⚠️  pip3 not found (may be needed for layer building)${NC}"
    fi
}

# Function to check jq
check_jq() {
    if command -v jq &> /dev/null; then
        echo -e "✅ jq is installed (for demo script)"
    else
        echo -e "${YELLOW}⚠️  jq not found (optional for demo script formatting)${NC}"
    fi
}

# Run all checks
echo "🔍 Checking required tools..."
check_aws_version
check_sam_version
check_python
check_pip3
check_jq

echo ""
echo "🔐 Checking AWS configuration..."
check_aws_credentials
check_region_support

echo ""
check_bedrock_models

echo ""
echo "=== Prerequisites Check Complete ==="

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ All prerequisites met! Ready to deploy.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. ./scripts/deploy.sh"
    echo "  2. ./scripts/test-demo.sh <API_ENDPOINT>"
    echo "  3. ./scripts/cleanup.sh (when done)"
    exit 0
else
    echo -e "${RED}❌ $ERRORS error(s) found. Please fix before deploying.${NC}"
    echo ""
    echo "Common fixes:"
    echo "  - Install Python 3.11+: https://www.python.org/downloads/"
    echo "  - Install AWS CLI v2: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"
    echo "  - Install SAM CLI: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html"
    echo "  - Configure AWS credentials: aws configure"
    echo "  - Install jq: brew install jq (macOS) or apt-get install jq (Linux)"
    echo "  - Install pip3: python3 -m ensurepip --upgrade"
    exit 1
fi