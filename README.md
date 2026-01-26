# Semantic Cache Demo

A demonstration of **semantic caching using AWS-native services** that reduces Amazon Bedrock LLM costs and latency through intelligent caching of semantically similar queries.

**Purpose:** Showcase how to implement semantic search and caching using only AWS services - no external vector databases or third-party dependencies required.

## 🎯 What This Demo Shows

- **Semantic Similarity Matching**: Different phrasings of the same question return cached responses
- **Vector Embeddings**: Using Amazon Titan Embeddings V2 (1024 dimensions)
- **Serverless Vector Storage**: Amazon S3 Vectors for native similarity search
- **LLM Integration**: Amazon Bedrock with Claude Haiku 4.5
- **Cost Optimization**: Cache hits are ~10x faster and avoid LLM costs

## 🚀 Quick Start

Deploy and test in 3 commands:

```bash
# 1. Check prerequisites
./scripts/check-prereqs.sh

# 2. Deploy infrastructure (⚠️ incurs AWS costs)
./scripts/deploy.sh

# 3. Test the demo
./scripts/test-demo.sh <API_ENDPOINT>

# 4. Clean up (IMPORTANT - avoid ongoing charges)
./scripts/cleanup.sh
```

## 📋 Prerequisites

### Required Tools
- **AWS CLI v2+**: `aws --version`
- **SAM CLI v1+**: `sam --version`
- **AWS Credentials**: `aws sts get-caller-identity`

### AWS Requirements
- **Supported Regions**: us-east-1, us-east-2, us-west-2, eu-west-1, ap-northeast-1
- **Bedrock Models**: Auto-enable on first use (no manual setup required)
  - Amazon Titan Embeddings V2 (`amazon.titan-embed-text-v2:0`)
  - Anthropic Claude Haiku 4.5 (`us.anthropic.claude-haiku-4-5-20251001-v1:0` - inference profile)

### Optional Tools
- **Python 3.12+**: For local testing
- **jq**: For demo script output formatting

## 💰 Cost Warning

**⚠️ This demo creates AWS resources that incur costs:**

| Resource | Estimated Cost | Notes |
|----------|----------------|-------|
| S3 Vectors | Usage-based | Storage + query costs |
| Lambda | ~$0.20/1M requests | Plus compute time |
| API Gateway HTTP | ~$1.00/1M requests | Minimal for demo usage |
| Bedrock Embeddings | ~$0.00002/1K tokens | Titan V2 |
| Bedrock LLM | ~$0.001/1K tokens | Claude Haiku 4.5 (input) |

**Estimated demo cost: < $1.00 for a few hours of testing**

**💡 Benefits of this architecture:**
- Fully serverless - no fixed infrastructure costs
- Pay only for what you use
- No minimum baseline charges

⚠️ *Verify current pricing at [AWS Pricing](https://aws.amazon.com/pricing/) - costs change frequently.*

**⚠️ CRITICAL: Run `./scripts/cleanup.sh` immediately after testing to avoid ongoing charges!**

## 🏗️ Architecture

![Semantic Cache Architecture](semantic_cache_architecture_updated.svg)

The semantic cache implements a 7-step flow:

```
1. Query → 2. Route → 3. Generate Embedding → 4. Vector Search
                                                      ↓
5a. Cache HIT (fast) ←─────────────────── Similarity ≥ 0.85?
                                                      ↓
5b. Cache MISS → 6. LLM Response → 7. Store in Cache
```

### Components

| Layer | Service | Purpose |
|-------|---------|---------|
| **API** | API Gateway HTTP API | REST endpoint with CORS |
| **Orchestration** | Lambda | Steps 2-7 coordination |
| **Cache** | Amazon S3 Vectors | Serverless vector search + storage |
| **AI/ML** | Amazon Bedrock | Embeddings + LLM responses |
| **Observability** | CloudWatch | Metrics + Dashboard |

### Key Features

- **Semantic Matching**: Different phrasings hit the same cache entry
- **Vector Search**: Native similarity search with S3 Vectors
- **Graceful Degradation**: Falls back to direct LLM if cache fails
- **Fully Serverless**: No VPC required, fast cold starts (~300ms)
- **AWS-Native**: Uses only AWS services - no external dependencies
- **Cost Effective**: Pay only for storage and queries used

### Security Model

This demo uses a **serverless security model** without VPC:

| Control | Implementation |
|---------|----------------|
| **Authentication** | IAM SigV4 for all AWS API calls |
| **Encryption in Transit** | TLS for all service communication |
| **Encryption at Rest** | AWS-managed encryption for S3 Vectors |
| **Rate Limiting** | API Gateway throttling (100 req/s burst) |
| **Input Validation** | Lambda validates all inputs |

**Why no VPC?** S3 Vectors and Bedrock are fully managed services accessed via authenticated APIs. VPC isolation is unnecessary and would add cold start latency.

## 🏭 Production Recommendations

This demo showcases the core semantic caching pattern. For production use, consider:

### Authentication & Authorization
- **API Gateway Authorizers**: Add Cognito, IAM, or Lambda authorizers
- **API Keys**: For client identification and usage tracking
- **AWS WAF**: Protect against common web exploits

### Scalability & Performance
- **Lambda Provisioned Concurrency**: Eliminate cold starts for consistent latency
- **Cache Warming**: Pre-populate cache with common queries
- **Multi-Region**: Deploy to multiple regions for global low latency

### Observability & Operations
- **X-Ray Tracing**: End-to-end request tracing
- **CloudWatch Alarms**: Alert on error rates, latency spikes
- **Custom Metrics**: Track cache hit rates, cost savings

### Data Management
- **TTL Strategy**: Implement cache expiration based on data freshness needs
- **Cache Invalidation**: API to clear stale entries when source data changes
- **Backup Strategy**: Regular exports of cached data if persistence is critical

### Cost Optimization
- **Reserved Capacity**: For Bedrock if usage is predictable
- **Similarity Threshold Tuning**: Balance hit rate vs response accuracy
- **Response Compression**: Reduce storage costs for large responses

## 🧪 Testing

### Run Unit Tests
```bash
cd tests
pip install -r requirements.txt
pytest unit/ -v
```

### Run Integration Tests
```bash
# Set API endpoint from deployment
export API_ENDPOINT="https://your-api-id.execute-api.us-east-1.amazonaws.com"
pytest integration/ -v
```

### Manual Testing
```bash
# Test cache miss (first time)
curl -X POST $API_ENDPOINT/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the capital of France?"}'

# Test cache hit (same query)
curl -X POST $API_ENDPOINT/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the capital of France?"}'

# Test semantic similarity
curl -X POST $API_ENDPOINT/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Tell me the capital city of France"}'
```

## 📊 Expected Results

| Test | Source | Latency | Similarity | Notes |
|------|--------|---------|------------|-------|
| First query | `bedrock` | ~3000ms | N/A | Cache miss - full LLM call |
| Same query | `cache` | ~300ms | 1.0 | Exact match - 10x faster |
| Similar phrasing | `cache` | ~400ms | ~0.93 | Semantic match |
| Different topic | `bedrock` | ~3000ms | N/A | Cache miss - different topic |

## 🔧 Configuration

Environment variables (set in CloudFormation):

| Variable | Default | Description |
|----------|---------|-------------|
| `SIMILARITY_THRESHOLD` | 0.85 | Minimum similarity for cache hit (0.0-1.0) |
| `VECTOR_BUCKET_NAME` | Auto | S3 Vectors bucket name (set by deployment) |
| `VECTOR_INDEX_NAME` | semanticcache | S3 Vectors index name |

## 📊 Monitoring

### CloudWatch Dashboard
Access via deployment output or:
```
https://us-east-1.console.aws.amazon.com/cloudwatch/home#dashboards:name=semantic-cache-demo-dashboard
```

### Key Metrics
- **Cache Hit Rate**: Percentage of requests served from cache
- **Latency**: Response times for cache hits vs misses
- **Request Count**: Total API requests
- **Error Rate**: Failed requests by type

### Logs
```bash
# View Lambda logs
aws logs tail /aws/lambda/semantic-cache-demo-handler --follow
```

## 🛠️ Development

### Project Structure
```
semantic-cache-demo/
├── infrastructure/
│   └── template.yaml              # Full CloudFormation template
├── src/cache_orchestrator/        # Lambda function code
│   ├── handler.py                 # Main orchestrator (Steps 2-7)
│   ├── embedding.py               # Titan Embeddings (Step 3)
│   ├── cache.py                   # S3 Vectors client (Steps 4,5a,7)
│   ├── llm.py                     # Claude LLM (Steps 5b,6)
│   └── metrics.py                 # CloudWatch metrics
├── scripts/                       # Deployment automation
└── tests/                         # Unit + integration tests
```

### Local Development
```bash
# Install dependencies
pip install -r src/cache_orchestrator/requirements.txt
pip install -r tests/requirements.txt

# Run tests
pytest tests/unit/ -v

# Deploy changes
cd infrastructure && sam build && sam deploy
```

## 🔧 Troubleshooting

| Issue | Quick Fix |
|-------|-----------|
| **Bedrock throttling** | Request quota increase: `./scripts/request-quota-increase.sh` |
| **Cache always misses** | Check S3 Vectors index: `aws s3vectors list-indexes --vector-bucket-name <bucket>` |
| **High latency** | Expected on first request (cold start). Check CloudWatch dashboard for metrics. |
| **Deployment fails** | Validate template: `sam validate --template infrastructure/template.yaml` |
| **Tests failing** | Install deps: `pip install -r tests/requirements.txt && pytest tests/ -v` |

**Common Commands:**
```bash
# View logs
aws logs tail /aws/lambda/semantic-cache-demo-handler --follow

# Check stack status
aws cloudformation describe-stacks --stack-name semantic-cache-demo

# Complete reset
./scripts/cleanup.sh && ./scripts/deploy.sh
```

## 🧹 Cleanup

**CRITICAL**: Always clean up after testing to avoid ongoing charges.

```bash
# Delete all resources
./scripts/cleanup.sh

# Verify cleanup completed
aws cloudformation describe-stacks --stack-name semantic-cache-demo
# Should return: "Stack with id semantic-cache-demo does not exist"

# Check for remaining costs
# https://console.aws.amazon.com/cost-management/home#/dashboard
```

The cleanup script removes:
- CloudFormation stack (all resources)
- S3 Vectors bucket and index
- CloudWatch log groups
- Local build artifacts

## 📚 Additional Resources

- **Full Specification**: `SPEC.md`
- **AWS Docs**: [Bedrock Models](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html) | [S3 Vectors](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors.html)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `pytest tests/ -v`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 💡 About This Demo

This project demonstrates **semantic caching using AWS-native services only**:

- **No external vector databases** - Uses Amazon S3 Vectors
- **No third-party LLM providers** - Uses Amazon Bedrock
- **No complex infrastructure** - Fully serverless, no VPC required
- **Production patterns** - Graceful degradation, retry logic, observability

**Use Cases**: Customer support bots, FAQ systems, documentation assistants, or any application with repetitive natural language queries.

**⚠️ This is a demonstration project.** For production deployment, implement the recommendations in the "Production Recommendations" section above.
