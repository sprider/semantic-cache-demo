#!/bin/bash
set -e

STACK_NAME="${1:-semantic-cache-demo}"

echo "=== Cleaning up Semantic Cache Demo ==="
echo "Stack: $STACK_NAME"
echo ""

# Confirmation prompt
echo "⚠️  This will DELETE ALL resources for the semantic cache demo:"
echo "   - S3 Vectors bucket and index"
echo "   - Lambda function and layer"
echo "   - API Gateway"
echo "   - CloudWatch Dashboard"
echo ""
read -p "Are you sure you want to delete everything? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled."
    exit 1
fi

echo ""
echo "🗑️  Deleting CloudFormation stack..."

# Check if stack exists
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" &> /dev/null; then
    echo "Stack found. Initiating deletion..."
    
    # Delete the stack
    aws cloudformation delete-stack --stack-name "$STACK_NAME"
    
    echo "⏳ Waiting for stack deletion to complete..."
    echo "   This may take 2-5 minutes..."
    
    # Wait for deletion with timeout
    if timeout 600 aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME"; then
        echo "✅ Stack deleted successfully"
    else
        echo "⚠️  Stack deletion timed out or failed"
        echo "   Check CloudFormation console for details:"
        REGION=$(aws configure get region)
        REGION=${REGION:-us-east-1}
        echo "   https://${REGION}.console.aws.amazon.com/cloudformation/home?region=${REGION}#/stacks"
        echo ""
        echo "   You may need to manually delete stuck resources"
    fi
else
    echo "Stack '$STACK_NAME' not found. Nothing to delete."
fi

echo ""
echo "🧹 Cleaning up additional resources..."

# Delete CloudWatch Log Groups (sometimes not deleted by CFN)
echo "Deleting CloudWatch Log Groups..."
LOG_GROUPS=$(aws logs describe-log-groups \
    --log-group-name-prefix "/aws/lambda/${STACK_NAME}" \
    --query 'logGroups[].logGroupName' \
    --output text 2>/dev/null || echo "")

if [ -n "$LOG_GROUPS" ]; then
    echo "$LOG_GROUPS" | tr '\t' '\n' | while read -r lg; do
        if [ -n "$lg" ]; then
            echo "  Deleting log group: $lg"
            aws logs delete-log-group --log-group-name "$lg" 2>/dev/null || true
        fi
    done
else
    echo "  No log groups found to delete"
fi

# Clean up local build artifacts
echo ""
echo "🧹 Cleaning up local build artifacts..."
if [ -d "infrastructure/.aws-sam" ]; then
    echo "  Removing .aws-sam build directory..."
    rm -rf infrastructure/.aws-sam
fi

if [ -f "infrastructure/packaged.yaml" ]; then
    echo "  Removing packaged.yaml..."
    rm -f infrastructure/packaged.yaml
fi

echo ""
echo "✅ Cleanup Complete!"
echo ""
echo "🔍 Verify no resources remain:"
echo "   aws cloudformation describe-stacks --stack-name $STACK_NAME"
echo "   (Should return: Stack with id $STACK_NAME does not exist)"
echo ""
echo "💰 Check for any remaining costs:"
echo "   https://console.aws.amazon.com/cost-management/home#/dashboard"
