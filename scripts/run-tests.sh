#!/bin/bash

echo "=== Running Semantic Cache Demo Unit Tests ==="
echo ""

# Set PYTHONPATH to include source directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src/cache_orchestrator"

# Run unit tests with coverage
echo "Running unit tests with coverage..."
python3 -m pytest tests/unit/ -v --cov=src/cache_orchestrator --cov-report=term-missing

echo ""
echo "=== Unit Tests Complete ==="
echo ""
echo "To run integration tests (requires deployed API):"
echo "  export API_ENDPOINT=https://your-api-endpoint.amazonaws.com/prod"
echo "  python3 -m pytest tests/integration/ -v"