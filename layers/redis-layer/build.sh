#!/bin/bash
set -e

echo "Building Redis Lambda Layer..."

# Clean previous build
rm -rf python/
rm -f redis-layer.zip

# Create layer structure
mkdir -p python/

# Install dependencies using pip3
pip3 install -r requirements.txt -t python/

# Create zip file
zip -r redis-layer.zip python/

echo "Redis layer built: redis-layer.zip"
echo "Size: $(du -h redis-layer.zip | cut -f1)"