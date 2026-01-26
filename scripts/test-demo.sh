#!/bin/bash

API_ENDPOINT="$1"

if [ -z "$API_ENDPOINT" ]; then
    echo "Usage: $0 <API_ENDPOINT>"
    echo ""
    echo "Get the API endpoint from the deploy script output or:"
    echo "  aws cloudformation describe-stacks --stack-name semantic-cache-demo --query 'Stacks[0].Outputs[?OutputKey==\`ApiEndpoint\`].OutputValue' --output text"
    exit 1
fi

echo "=== Semantic Cache Demo Test ==="
echo "API Endpoint: $API_ENDPOINT"
echo ""

# Function to make API call and format output
make_request() {
    local query="$1"
    local step_description="$2"
    
    echo "$step_description"
    echo "Query: \"$query\""
    echo ""
    
    # Make the request and capture response
    RESPONSE=$(curl -s -X POST "$API_ENDPOINT/query" \
        -H "Content-Type: application/json" \
        -d "{\"query\": \"$query\"}" \
        --max-time 30)
    
    # Check if jq is available for pretty printing
    if command -v jq &> /dev/null; then
        echo "$RESPONSE" | jq .
    else
        echo "$RESPONSE"
    fi
    
    # Extract key metrics if jq is available
    if command -v jq &> /dev/null && echo "$RESPONSE" | jq . &> /dev/null; then
        SOURCE=$(echo "$RESPONSE" | jq -r '.source // "unknown"')
        LATENCY=$(echo "$RESPONSE" | jq -r '.latency_ms // "unknown"')
        SIMILARITY=$(echo "$RESPONSE" | jq -r '.similarity // "N/A"')
        
        echo ""
        echo "📊 Metrics: Source=$SOURCE, Latency=${LATENCY}ms, Similarity=$SIMILARITY"
    fi
    
    echo ""
    echo "---"
    echo ""
}

echo "🧪 Testing Semantic Cache Flow (Steps 1-7)..."
echo ""

# Test 1: First query (cache miss path - Steps 1,2,3,4,5b,6,7)
make_request "What is the capital of France?" "🔍 Test 1: First query (Cache MISS - Steps 1→2→3→4→5b→6→7)"

sleep 2

# Test 2: Same query (cache hit path - Steps 1,2,3,4,5a)
make_request "What is the capital of France?" "⚡ Test 2: Identical query (Cache HIT - Steps 1→2→3→4→5a)"

sleep 2

# Test 3: Similar query (should be cache hit due to semantic similarity)
make_request "Tell me the capital city of France" "🎯 Test 3: Semantically similar query (Cache HIT - Steps 1→2→3→4→5a)"

sleep 2

# Test 4: Different query (cache miss path)
make_request "What is machine learning?" "🆕 Test 4: Different topic (Cache MISS - Steps 1→2→3→4→5b→6→7)"

sleep 2

# Test 5: Another similar query to first topic
make_request "Which city is the capital of France?" "🔄 Test 5: Another similar query (Cache HIT - Steps 1→2→3→4→5a)"

echo ""
echo "=== Demo Complete ==="
echo ""
echo "📈 Expected Results:"
echo "   - Test 1: source=bedrock, latency ~3000-4000ms (cache miss)"
echo "   - Test 2: source=cache, similarity=1.0, latency ~300ms (exact match)"
echo "   - Test 3: source=cache, similarity~0.93, latency ~400ms (semantic match)"
echo "   - Test 4: source=bedrock, latency ~3000-15000ms (different topic)"
echo "   - Test 5: source=cache, similarity~0.98, latency ~300ms (semantic match)"
echo ""
echo "🎯 Key Observations:"
echo "   - Cache HITs are ~10x faster than cache MISSes"
echo "   - Semantic similarity allows different phrasings to hit cache"
echo "   - Similarity threshold (0.85) determines hit vs miss"
echo ""
echo "📊 View metrics in CloudWatch Dashboard:"
STACK_NAME="${STACK_NAME:-semantic-cache-demo}"
REGION=$(aws configure get region)
REGION=${REGION:-us-east-1}
echo "   https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards:name=${STACK_NAME}-dashboard"
echo ""
echo "⚠️  IMPORTANT: To avoid ongoing charges, run:"
echo "   ./scripts/cleanup.sh"
echo ""
echo "Resources will continue to incur costs until deleted."