#!/bin/bash
set -e

STACK_NAME="${1:-semantic-cache-demo}"

echo "=== Semantic Cache Demo Deployment ==="
echo "Stack: $STACK_NAME"
echo ""

# Cost warning
echo "⚠️  WARNING: This will create AWS resources that incur costs:"
echo ""
echo "   Resources created:"
echo "   - S3 Vectors bucket and index (usage-based pricing)"
echo "   - Lambda function (~\$0.20 per 1M requests)"
echo "   - API Gateway HTTP API (~\$1.00 per 1M requests)"
echo "   - Bedrock API calls (per-token pricing)"
echo ""
echo "   💡 Fully serverless - pay only for what you use"
echo ""
echo "💰 Estimated demo cost: < \$1.00 for a few hours of testing"
echo "   (Verify current pricing at https://aws.amazon.com/pricing/)"
echo ""
echo "🧹 DELETE IMMEDIATELY after testing to avoid charges:"
echo "   ./scripts/cleanup.sh"
echo ""
read -p "I understand the costs. Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 1
fi

echo ""
echo "🚀 Starting deployment..."

# Check if we're in the right directory
if [ ! -f "infrastructure/template.yaml" ]; then
    echo "❌ Error: infrastructure/template.yaml not found"
    echo "   Run this script from the project root directory"
    exit 1
fi

# Build Redis layer (kept for compatibility)
echo ""
echo "📦 Building Lambda layer..."
if [ -f "layers/redis-layer/build.sh" ]; then
    chmod +x layers/redis-layer/build.sh
    cd layers/redis-layer
    ./build.sh
    cd ../..
    echo "✅ Lambda layer built successfully"
else
    echo "⚠️  Lambda layer build script not found, continuing..."
fi

# Build SAM application
echo ""
echo "🏗️  Building SAM application..."
cd infrastructure
sam build --template-file template.yaml

echo ""
echo "🚀 Deploying to AWS..."
sam deploy \
    --template-file template.yaml \
    --stack-name "$STACK_NAME" \
    --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
    --resolve-s3 \
    --no-confirm-changeset \
    --parameter-overrides \
        ProjectName="$STACK_NAME"

# Get the API endpoint
API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
    --output text)

DASHBOARD_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`DashboardURL`].OutputValue' \
    --output text)

VECTOR_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`VectorBucketName`].OutputValue' \
    --output text)

echo ""
echo "🎉 Deployment Complete!"
echo ""
echo "📊 Resources Created:"
echo "   - S3 Vectors bucket: $VECTOR_BUCKET"
echo "   - S3 Vectors index: semanticcache"
echo "   - Lambda function (serverless, no VPC)"
echo "   - API Gateway HTTP API"
echo "   - CloudWatch Dashboard"
echo ""
echo "🔗 Endpoints:"
echo "   API: $API_ENDPOINT"
echo "   Dashboard: $DASHBOARD_URL"
echo ""
echo "🧪 Test the deployment:"
echo "   ./scripts/test-demo.sh $API_ENDPOINT"
echo ""
echo "⚠️  IMPORTANT: Resources are now incurring costs!"
echo "   Run './scripts/cleanup.sh' when done to avoid charges."

cd ..
