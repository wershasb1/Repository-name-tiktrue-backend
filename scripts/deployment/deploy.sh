#!/bin/bash
# TikTrue Platform Deployment Script for Unix/Linux/macOS
# This script provides an easy interface to the Python deployment orchestrator

set -e  # Exit on any error

echo "========================================"
echo "TikTrue Platform Deployment Tool"
echo "========================================"
echo

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.11+ and try again"
    exit 1
fi

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT"

# Check if deployment script exists
if [ ! -f "$SCRIPT_DIR/deploy.py" ]; then
    echo "ERROR: deploy.py not found in $SCRIPT_DIR"
    exit 1
fi

# Parse command line arguments
DRY_RUN=""
CONFIG_FILE=""
ROLLBACK=""
BACKUP_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --config)
            CONFIG_FILE="--config $2"
            shift 2
            ;;
        --rollback)
            ROLLBACK="--rollback"
            shift
            ;;
        --backup-id)
            BACKUP_ID="--backup-id $2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run] [--config CONFIG_FILE] [--rollback] [--backup-id BACKUP_ID]"
            exit 1
            ;;
    esac
done

# Show menu if no arguments provided
if [ -z "$DRY_RUN$CONFIG_FILE$ROLLBACK" ]; then
    echo "Select deployment option:"
    echo
    echo "1. Full deployment"
    echo "2. Dry run (test without executing)"
    echo "3. Rollback to previous deployment"
    echo "4. Exit"
    echo
    read -p "Enter your choice (1-4): " choice
    
    case $choice in
        1)
            echo
            echo "Starting full deployment..."
            echo
            python3 "$SCRIPT_DIR/deploy.py" $CONFIG_FILE
            ;;
        2)
            echo
            echo "Starting dry run deployment..."
            echo
            python3 "$SCRIPT_DIR/deploy.py" --dry-run $CONFIG_FILE
            ;;
        3)
            echo
            echo "Available backups:"
            if [ -d "$PROJECT_ROOT/temp/deployment_backups" ]; then
                ls -1 "$PROJECT_ROOT/temp/deployment_backups"
            else
                echo "No backups found."
                exit 1
            fi
            echo
            read -p "Enter backup ID to rollback to (or press Enter to cancel): " backup_id
            if [ -z "$backup_id" ]; then
                echo "Rollback cancelled."
                exit 0
            fi
            
            echo
            echo "Starting rollback to backup: $backup_id"
            echo
            python3 "$SCRIPT_DIR/deploy.py" --rollback --backup-id "$backup_id"
            ;;
        4)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid choice. Please try again."
            exit 1
            ;;
    esac
else
    # Execute with provided arguments
    if [ -n "$ROLLBACK" ]; then
        echo
        echo "Starting rollback..."
        echo
        python3 "$SCRIPT_DIR/deploy.py" $ROLLBACK $BACKUP_ID
    else
        echo
        echo "Starting deployment..."
        echo
        python3 "$SCRIPT_DIR/deploy.py" $DRY_RUN $CONFIG_FILE
    fi
fi

echo
echo "Deployment process completed."
echo "Check the logs in temp/logs/ for detailed information."
echo

# Make the script executable
chmod +x "$0" 2>/dev/null || true