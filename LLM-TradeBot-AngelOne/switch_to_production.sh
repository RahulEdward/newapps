#!/bin/bash

# ============================================================================
# Data Source Switch Quick Configuration Script
# ============================================================================
# Purpose: Help users quickly switch to Binance production environment
# Usage: chmod +x switch_to_production.sh && ./switch_to_production.sh
# ============================================================================

set -e  # Exit immediately on error

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║$1${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# ============================================================================
# Step 1: Check Environment
# ============================================================================
check_environment() {
    print_header "  Step 1: Check Environment                                    "
    
    # Check config file
    if [ ! -f "config.yaml" ]; then
        print_error "config.yaml does not exist"
        echo "Please copy config.example.yaml first:"
        echo "  cp config.example.yaml config.yaml"
        exit 1
    fi
    print_success "config.yaml exists"
    
    if [ ! -f ".env" ]; then
        print_warning ".env does not exist, will copy from .env.example"
        cp .env.example .env
        print_success ".env file created"
    else
        print_success ".env exists"
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "python3 not found"
        exit 1
    fi
    print_success "Python environment OK"
}

# ============================================================================
# Step 2: Configure API Keys
# ============================================================================
configure_api_keys() {
    print_header "  Step 2: Configure API Keys                                   "
    
    echo ""
    print_info "Please enter your Binance API keys"
    echo ""
    echo "How to get:"
    echo "  1. Login to https://www.binance.com"
    echo "  2. Account → API Management"
    echo "  3. Create API Key"
    echo ""
    print_warning "Important: Make sure you trust this script, keys will be written to .env file"
    echo ""
    
    # Read API Key
    read -p "Binance API Key (leave empty to skip): " api_key
    
    if [ -z "$api_key" ]; then
        print_warning "Skipping API key configuration"
        print_info "Please manually edit .env file to configure keys"
        return
    fi
    
    # Read API Secret
    read -sp "Binance API Secret: " api_secret
    echo ""
    
    if [ -z "$api_secret" ]; then
        print_error "API Secret cannot be empty"
        return
    fi
    
    # Write to .env
    # Use sed to replace or append
    if grep -q "BINANCE_API_KEY=" .env; then
        # macOS compatible sed
        sed -i '' "s/BINANCE_API_KEY=.*/BINANCE_API_KEY=${api_key}/" .env
        sed -i '' "s/BINANCE_API_SECRET=.*/BINANCE_API_SECRET=${api_secret}/" .env
    else
        echo "BINANCE_API_KEY=${api_key}" >> .env
        echo "BINANCE_API_SECRET=${api_secret}" >> .env
    fi
    
    print_success "API keys configured in .env file"
}

# ============================================================================
# Step 3: Switch to Production Environment
# ============================================================================
switch_to_production() {
    print_header "  Step 3: Switch to Production Environment                     "
    
    echo ""
    print_warning "About to switch to Binance production environment"
    print_warning "This will use real market data and account"
    echo ""
    read -p "Confirm to continue? (y/N): " confirm
    
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        print_info "Operation cancelled"
        exit 0
    fi
    
    # Backup config file
    cp config.yaml config.yaml.backup
    print_success "Config file backed up to config.yaml.backup"
    
    # Modify testnet config
    # macOS compatible sed
    sed -i '' 's/testnet: true/testnet: false/' config.yaml
    
    print_success "Switched to production environment (testnet: false)"
    
    # Show current config
    echo ""
    print_info "Current configuration:"
    grep "testnet:" config.yaml
}

# ============================================================================
# Step 4: Run Tests
# ============================================================================
run_tests() {
    print_header "  Step 4: Run Connection Tests                                 "
    
    echo ""
    print_info "Testing API connection..."
    echo ""
    
    # Run test script
    if python3 test_binance_connection.py; then
        print_success "Connection test passed!"
        return 0
    else
        print_error "Connection test failed"
        print_info "Please check:"
        echo "  1. Are API keys correct"
        echo "  2. Are API permissions sufficient"
        echo "  3. Is IP in whitelist"
        echo "  4. Is network connection normal"
        return 1
    fi
}

# ============================================================================
# Step 5: Summary
# ============================================================================
print_summary() {
    print_header "  Configuration Complete                                       "
    
    echo ""
    print_success "Data source switched to Binance production environment"
    echo ""
    echo "Next steps:"
    echo "  1. Run data pipeline script to verify data quality:"
    echo "     python show_data_pipeline.py"
    echo ""
    echo "  2. View detailed documentation:"
    echo "     cat DATA_SOURCE_MIGRATION_GUIDE.md"
    echo ""
    echo "  3. To rollback to testnet:"
    echo "     sed -i '' 's/testnet: false/testnet: true/' config.yaml"
    echo ""
    
    print_warning "Security reminders:"
    echo "  • Never share your API keys"
    echo "  • Regularly check API permissions"
    echo "  • Test with small amounts first"
    echo "  • Set reasonable risk control parameters"
    echo ""
}

# ============================================================================
# Main Function
# ============================================================================
main() {
    clear
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║       Data Source Switch Script - Binance Production           ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Execute steps
    check_environment
    echo ""
    
    configure_api_keys
    echo ""
    
    switch_to_production
    echo ""
    
    if run_tests; then
        echo ""
        print_summary
        exit 0
    else
        echo ""
        print_error "Error occurred during configuration"
        print_info "Config file backed up to config.yaml.backup"
        print_info "To restore: mv config.yaml.backup config.yaml"
        exit 1
    fi
}

# Run main function
main
