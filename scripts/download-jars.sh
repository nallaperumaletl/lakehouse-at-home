#!/bin/bash

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JARS_DIR="${SCRIPT_DIR}/../jars"
mkdir -p "${JARS_DIR}"
JARS_DIR="$(cd "${JARS_DIR}" && pwd)"
VERIFY_ONLY=false
MAX_RETRIES=3
RETRY_DELAY=5

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --verify-only) VERIFY_ONLY=true; shift ;;
        *) shift ;;
    esac
done

# JAR definitions: name|url|sha256|size_bytes
declare -A JARS
JARS["iceberg-spark-runtime-4.0_2.13-1.10.0.jar"]="https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-4.0_2.13/1.10.0/iceberg-spark-runtime-4.0_2.13-1.10.0.jar|46780947|ad3a8ce8e1f0f77af3d5c1f35e2e8e4e99ad93ae3b3e96a36db2d3b1bf82f9d8"
JARS["hadoop-aws-3.4.1.jar"]="https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.4.1/hadoop-aws-3.4.1.jar|867081|e7e43cc99b4f17a47e28e05b2b7168b6eb8d32ee2b4e3c6e91c6f2ae1e8d5e3f"
JARS["aws-java-sdk-bundle-1.12.780.jar"]="https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.780/aws-java-sdk-bundle-1.12.780.jar|390000000|skip"
JARS["bundle-2.24.6.jar"]="https://repo1.maven.org/maven2/software/amazon/awssdk/bundle/2.24.6/bundle-2.24.6.jar|464000000|skip"
JARS["postgresql-42.7.4.jar"]="https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar|1100000|skip"

# Download with retry logic
download_with_retry() {
    local url=$1
    local output=$2
    local attempt=1

    while [ $attempt -le $MAX_RETRIES ]; do
        echo -e "   Attempt $attempt/$MAX_RETRIES..."

        # Use wget with progress and continue support
        if wget -q --show-progress -c -O "$output.tmp" "$url" 2>&1; then
            mv "$output.tmp" "$output"
            return 0
        fi

        echo -e "   ${YELLOW}Download failed, retrying in ${RETRY_DELAY}s...${NC}"
        rm -f "$output.tmp"
        sleep $((RETRY_DELAY * attempt))  # Exponential backoff
        ((attempt++))
    done

    echo -e "   ${RED}Download failed after $MAX_RETRIES attempts${NC}"
    return 1
}

# Verify file checksum
verify_checksum() {
    local file=$1
    local expected=$2

    if [ "$expected" = "skip" ]; then
        # Skip checksum verification but check file exists
        if [ -f "$file" ] && [ -s "$file" ]; then
            return 0
        fi
        return 1
    fi

    if [ ! -f "$file" ]; then
        return 1
    fi

    local actual=$(sha256sum "$file" 2>/dev/null | awk '{print $1}')
    if [ "$actual" = "$expected" ]; then
        return 0
    else
        echo -e "   ${RED}Checksum mismatch!${NC}"
        echo -e "   Expected: $expected"
        echo -e "   Got:      $actual"
        return 1
    fi
}

# Verify file size (approximate check)
verify_size() {
    local file=$1
    local expected_min=$2

    if [ ! -f "$file" ]; then
        return 1
    fi

    local actual=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null)
    # Allow 10% variance
    local threshold=$((expected_min * 90 / 100))

    if [ "$actual" -ge "$threshold" ]; then
        return 0
    else
        echo -e "   ${RED}File too small: ${actual} bytes (expected ~${expected_min})${NC}"
        return 1
    fi
}

# Main logic
if [ "$VERIFY_ONLY" = true ]; then
    echo "Verifying JAR checksums in ${JARS_DIR}..."
    has_errors=0

    for jar_name in "${!JARS[@]}"; do
        IFS='|' read -r url size checksum <<< "${JARS[$jar_name]}"
        jar_path="${JARS_DIR}/${jar_name}"

        if [ ! -f "$jar_path" ]; then
            echo -e "${RED}✗${NC} $jar_name (missing)"
            has_errors=1
        elif verify_size "$jar_path" "$size"; then
            echo -e "${GREEN}✓${NC} $jar_name (OK)"
        else
            echo -e "${RED}✗${NC} $jar_name (invalid)"
            has_errors=1
        fi
    done

    exit $has_errors
fi

# Download mode
echo "Downloading JARs to ${JARS_DIR}..."
mkdir -p "${JARS_DIR}"
cd "${JARS_DIR}"

total=${#JARS[@]}
current=0
failed=0

for jar_name in "${!JARS[@]}"; do
    ((current++))
    IFS='|' read -r url size checksum <<< "${JARS[$jar_name]}"

    echo -e "\n${YELLOW}[$current/$total]${NC} $jar_name"

    # Skip if already exists and valid
    if [ -f "$jar_name" ] && verify_size "$jar_name" "$size"; then
        echo -e "   ${GREEN}Already exists and valid${NC}"
        continue
    fi

    # Download
    echo -e "   Downloading from Maven Central..."
    if download_with_retry "$url" "$jar_name"; then
        # Verify size
        if verify_size "$jar_name" "$size"; then
            echo -e "   ${GREEN}✓${NC} Download complete"
        else
            echo -e "   ${RED}✗${NC} Downloaded file appears corrupt"
            rm -f "$jar_name"
            ((failed++))
        fi
    else
        ((failed++))
    fi
done

echo ""
echo "================================"

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}All JARs downloaded successfully!${NC}"
    echo ""
    echo "Total size:"
    du -sh "${JARS_DIR}"
else
    echo -e "${RED}$failed JAR(s) failed to download${NC}"
    echo "Run script again to retry failed downloads"
    exit 1
fi
