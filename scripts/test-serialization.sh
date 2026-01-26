#!/bin/bash

API_ENDPOINT="$1"

if [ -z "$API_ENDPOINT" ]; then
    echo "Usage: $0 <API_ENDPOINT>"
    echo ""
    echo "This script tests that Bedrock calls are properly serialized"
    echo "by sending multiple concurrent requests and checking timing."
    exit 1
fi

echo "=== Testing Bedrock Call Serialization ==="
echo "API Endpoint: $API_ENDPOINT"
echo ""

echo "🧪 Sending 3 concurrent requests to test enhanced serialization..."
echo "Expected: Requests should be processed sequentially due to:"
echo "  - Lambda Reserved Concurrency: 1"
echo "  - Enhanced file-based rate limiting with request distribution"
echo "  - Minimum 2 seconds + jitter between Bedrock calls"
echo "  - Adaptive retry with 10 max attempts"
echo "  - Quota-aware timing synchronization"
echo ""

# Function to make a request and measure time
make_timed_request() {
    local query="$1"
    local start_time=$(date +%s)
    
    echo "[$start_time] Starting request: \"$query\""
    
    RESPONSE=$(curl -s -X POST "$API_ENDPOINT/query" \
        -H "Content-Type: application/json" \
        -d "{\"query\": \"$query\"}" \
        --max-time 60)
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo "[$end_time] Completed request: \"$query\" (${duration}s)"
    
    # Check if response contains expected fields
    if echo "$RESPONSE" | grep -q '"response"'; then
        echo "  ✅ Success: Got valid response"
    elif echo "$RESPONSE" | grep -q '"error"'; then
        echo "  ⚠️  Error response: $(echo "$RESPONSE" | head -c 100)..."
    else
        echo "  ❌ Unexpected response: $(echo "$RESPONSE" | head -c 100)..."
    fi
    echo ""
}

# Send concurrent requests in background
make_timed_request "What is AI?" &
PID1=$!

make_timed_request "Explain machine learning" &
PID2=$!

make_timed_request "Define neural networks" &
PID3=$!

# Wait for all requests to complete
echo "⏳ Waiting for all requests to complete..."
wait $PID1
wait $PID2
wait $PID3

echo ""
echo "=== Serialization Test Complete ==="
echo ""
echo "📊 Expected Behavior:"
echo "  - Requests should complete sequentially (not simultaneously)"
echo "  - Total time should be ~6-9 seconds (2s + jitter per request)"
echo "  - No concurrent Bedrock API calls should occur"
echo "  - Enhanced retry logic should handle quota limits gracefully"
echo ""
echo "🔍 Check CloudWatch logs to verify enhanced serialization:"
echo "  aws logs tail /aws/lambda/semantic-cache-demo-handler --follow"
echo ""
echo "💡 If requests still fail with throttling:"
echo "  1. Check AWS Service Quotas console for Bedrock limits"
echo "  2. Monitor CloudWatch metrics: InputTokenCount, Invocations"
echo "  3. Consider cross-region inference profiles"
echo "  4. Request Bedrock quota increase with ./scripts/request-quota-increase.sh"
echo "  5. Try different AWS region with higher quotas"