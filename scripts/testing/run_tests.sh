#!/bin/bash
# TikTrue End-to-End Testing Script

echo "TikTrue Platform - End-to-End Testing Suite"
echo "==========================================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed"
    exit 1
fi

# Check if required Python packages are available
python3 -c "import requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing required Python packages..."
    pip3 install requests
fi

# Create results directory
RESULTS_DIR="test_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"

echo "Test results will be saved to: $RESULTS_DIR"
echo ""

# Run the main test suite
echo "Running comprehensive end-to-end tests..."
python3 "$(dirname "$0")/run_e2e_tests.py" | tee "$RESULTS_DIR/test_output.log"

# Capture exit code
TEST_EXIT_CODE=${PIPESTATUS[0]}

# Move generated report files to results directory
mv e2e_test_report_*.json "$RESULTS_DIR/" 2>/dev/null

# Additional quick tests
echo ""
echo "Running additional quick tests..."

# Test website response time
echo "Testing website response time..."
RESPONSE_TIME=$(curl -o /dev/null -s -w "%{time_total}" https://tiktrue.com)
echo "Website response time: ${RESPONSE_TIME}s" | tee -a "$RESULTS_DIR/performance.log"

# Test API response time
echo "Testing API response time..."
API_RESPONSE_TIME=$(curl -o /dev/null -s -w "%{time_total}" https://api.tiktrue.com/api/health/)
echo "API response time: ${API_RESPONSE_TIME}s" | tee -a "$RESULTS_DIR/performance.log"

# Test SSL certificate expiration
echo "Checking SSL certificate..."
SSL_INFO=$(echo | openssl s_client -servername tiktrue.com -connect tiktrue.com:443 2>/dev/null | openssl x509 -noout -dates)
echo "SSL Certificate Info:" | tee -a "$RESULTS_DIR/ssl_info.log"
echo "$SSL_INFO" | tee -a "$RESULTS_DIR/ssl_info.log"

# Generate final summary
echo ""
echo "=========================================="
echo "TESTING COMPLETED"
echo "=========================================="
echo "Results directory: $RESULTS_DIR"
echo "Main test exit code: $TEST_EXIT_CODE"

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "Status: ALL TESTS PASSED ✓"
else
    echo "Status: SOME TESTS FAILED ✗"
fi

echo ""
echo "Files generated:"
ls -la "$RESULTS_DIR/"

exit $TEST_EXIT_CODE