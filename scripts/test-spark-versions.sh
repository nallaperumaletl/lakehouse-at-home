#!/bin/bash

# Multi-version Spark testing script
# Runs tests against both Spark 4.0 and 4.1 versions

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default settings
SPARK_VERSIONS=("4.1")  # Default to Spark 4.1
TEST_TYPE="unit"  # unit, integration, all
PARALLEL=false
CLEANUP=true

# Spark version configuration
declare -A SPARK_IMAGES
SPARK_IMAGES["4.0"]="apache/spark:4.0.1-scala2.13-java17-python3-r-ubuntu"
SPARK_IMAGES["4.1"]="apache/spark:4.1.0-scala2.13-java21-python3-r-ubuntu"

declare -A SPARK_PORTS
SPARK_PORTS["4.0"]="7077"
SPARK_PORTS["4.1"]="7078"

declare -A SPARK_UI_PORTS
SPARK_UI_PORTS["4.0"]="8080"
SPARK_UI_PORTS["4.1"]="8082"

declare -A SPARK_COMPOSE
SPARK_COMPOSE["4.0"]="docker-compose.yml"
SPARK_COMPOSE["4.1"]="docker-compose-spark41.yml"

usage() {
    echo "Multi-version Spark Testing Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -v, --version VERSION   Test specific Spark version (4.0 or 4.1)"
    echo "  -t, --type TYPE         Test type: unit, integration, all (default: unit)"
    echo "  -p, --parallel          Run version tests in parallel"
    echo "  --no-cleanup            Don't stop containers after tests"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                      # Run unit tests on Spark 4.1 (default)"
    echo "  $0 -v 4.0               # Run unit tests on Spark 4.0"
    echo "  $0 -v 4.0 -v 4.1        # Run unit tests on both versions"
    echo "  $0 -t integration       # Run integration tests on Spark 4.1"
    echo "  $0 -t all -p            # Run all tests in parallel"
}

# Track if user explicitly set versions
USER_SET_VERSIONS=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--version)
            if [ "$USER_SET_VERSIONS" = false ]; then
                SPARK_VERSIONS=("$2")
                USER_SET_VERSIONS=true
            else
                SPARK_VERSIONS+=("$2")
            fi
            shift 2
            ;;
        -t|--type)
            TEST_TYPE="$2"
            shift 2
            ;;
        -p|--parallel)
            PARALLEL=true
            shift
            ;;
        --no-cleanup)
            CLEANUP=false
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

header() {
    echo -e "\n${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Check if Docker is running
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        echo -e "${RED}Error: Docker is not running${NC}"
        exit 1
    fi
}

# Start Spark cluster for a specific version
start_spark() {
    local version=$1
    local compose_file="${SPARK_COMPOSE[$version]}"

    echo -e "${YELLOW}Starting Spark $version cluster...${NC}"

    if [ ! -f "$compose_file" ]; then
        echo -e "${RED}Error: $compose_file not found${NC}"
        return 1
    fi

    docker compose -f "$compose_file" up -d

    # Wait for Spark to be ready
    local port="${SPARK_PORTS[$version]}"
    local max_attempts=30
    local attempt=1

    echo -n "Waiting for Spark master"
    while [ $attempt -le $max_attempts ]; do
        if nc -z localhost "$port" 2>/dev/null; then
            echo -e " ${GREEN}Ready${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done

    echo -e " ${RED}Timeout${NC}"
    return 1
}

# Stop Spark cluster for a specific version
stop_spark() {
    local version=$1
    local compose_file="${SPARK_COMPOSE[$version]}"

    echo -e "${YELLOW}Stopping Spark $version cluster...${NC}"
    docker compose -f "$compose_file" down 2>/dev/null || true
}

# Run tests for a specific Spark version
run_tests() {
    local version=$1
    local test_type=$2
    local exit_code=0

    header "Testing Spark $version ($test_type)"

    export SPARK_VERSION="$version"
    export SPARK_MASTER_PORT="${SPARK_PORTS[$version]}"
    export SPARK_UI_PORT="${SPARK_UI_PORTS[$version]}"

    case $test_type in
        unit)
            echo -e "${YELLOW}Running unit tests...${NC}"
            poetry run pytest tests/ \
                --ignore=tests/integration/ \
                -m "not integration" \
                -v \
                --tb=short \
                || exit_code=$?
            ;;
        integration)
            echo -e "${YELLOW}Running integration tests...${NC}"
            # Start Spark for integration tests
            start_spark "$version" || return 1

            poetry run pytest tests/integration/ \
                -m "integration" \
                -v \
                --tb=short \
                --timeout=300 \
                || exit_code=$?

            if [ "$CLEANUP" = true ]; then
                stop_spark "$version"
            fi
            ;;
        all)
            echo -e "${YELLOW}Running all tests...${NC}"
            start_spark "$version" || return 1

            poetry run pytest tests/ \
                -v \
                --tb=short \
                --timeout=300 \
                || exit_code=$?

            if [ "$CLEANUP" = true ]; then
                stop_spark "$version"
            fi
            ;;
    esac

    return $exit_code
}

# Run Spark job validation
validate_spark() {
    local version=$1
    local image="${SPARK_IMAGES[$version]}"

    header "Validating Spark $version"

    echo -e "${YELLOW}Running SparkPi example...${NC}"
    docker run --rm "$image" \
        /opt/spark/bin/spark-submit \
        --master "local[2]" \
        --class org.apache.spark.examples.SparkPi \
        "/opt/spark/examples/jars/spark-examples_2.13-${version}.1.jar" 5

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Spark $version validation passed${NC}"
        return 0
    else
        echo -e "${RED}Spark $version validation failed${NC}"
        return 1
    fi
}

# Main execution
main() {
    check_docker

    header "Multi-version Spark Testing"
    echo "Versions: ${SPARK_VERSIONS[*]}"
    echo "Test type: $TEST_TYPE"
    echo "Parallel: $PARALLEL"

    local failed_versions=()
    local pids=()

    for version in "${SPARK_VERSIONS[@]}"; do
        if [ "$PARALLEL" = true ]; then
            # Run in background
            (
                run_tests "$version" "$TEST_TYPE"
            ) &
            pids+=($!)
        else
            # Run sequentially
            if ! run_tests "$version" "$TEST_TYPE"; then
                failed_versions+=("$version")
            fi
        fi
    done

    # Wait for parallel jobs
    if [ "$PARALLEL" = true ]; then
        for i in "${!pids[@]}"; do
            if ! wait "${pids[$i]}"; then
                failed_versions+=("${SPARK_VERSIONS[$i]}")
            fi
        done
    fi

    # Summary
    header "Test Summary"

    if [ ${#failed_versions[@]} -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        echo "Tested versions: ${SPARK_VERSIONS[*]}"
        exit 0
    else
        echo -e "${RED}Tests failed for: ${failed_versions[*]}${NC}"
        exit 1
    fi
}

# Cleanup on exit
cleanup() {
    if [ "$CLEANUP" = true ]; then
        for version in "${SPARK_VERSIONS[@]}"; do
            stop_spark "$version" 2>/dev/null || true
        done
    fi
}

trap cleanup EXIT

main "$@"
