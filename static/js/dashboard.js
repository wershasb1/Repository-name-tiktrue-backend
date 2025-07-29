/**
 * TikTrue Network Health Dashboard JavaScript
 */

// Global variables
let refreshInterval = 5000; // Default refresh interval in ms
let refreshTimer = null;
let errorLog = [];

/**
 * Initialize dashboard
 * @param {number} interval - Refresh interval in milliseconds
 */
function initDashboard(interval) {
    // Set refresh interval
    refreshInterval = interval || 5000;
    
    // Initial data load
    refreshDashboard();
    
    // Setup event listeners
    document.getElementById('refresh-btn').addEventListener('click', refreshDashboard);
    document.getElementById('auto-refresh').addEventListener('change', toggleAutoRefresh);
    document.getElementById('clear-errors-btn').addEventListener('click', clearErrorLog);
    
    // Start auto-refresh
    startAutoRefresh();
}

/**
 * Start auto-refresh timer
 */
function startAutoRefresh() {
    if (document.getElementById('auto-refresh').checked) {
        stopAutoRefresh(); // Clear any existing timer
        refreshTimer = setInterval(refreshDashboard, refreshInterval);
    }
}

/**
 * Stop auto-refresh timer
 */
function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

/**
 * Toggle auto-refresh based on checkbox
 */
function toggleAutoRefresh() {
    if (document.getElementById('auto-refresh').checked) {
        startAutoRefresh();
    } else {
        stopAutoRefresh();
    }
}

/**
 * Refresh dashboard data
 */
function refreshDashboard() {
    // Show loading indicator
    const refreshBtn = document.getElementById('refresh-btn');
    refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Refreshing...';
    refreshBtn.disabled = true;
    
    // Fetch status data
    fetch('/api/status')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            updateDashboard(data);
        })
        .catch(error => {
            console.error('Error fetching dashboard data:', error);
            addErrorToLog('Dashboard', `Failed to fetch data: ${error.message}`);
        })
        .finally(() => {
            // Reset refresh button
            refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Refresh';
            refreshBtn.disabled = false;
        });
}

/**
 * Update dashboard with new data
 * @param {Object} data - Dashboard data
 */
function updateDashboard(data) {
    // Update summary cards
    document.getElementById('total-networks').textContent = data.total_networks || 0;
    document.getElementById('running-networks').textContent = data.running_networks || 0;
    document.getElementById('total-requests').textContent = data.total_requests || 0;
    document.getElementById('total-errors').textContent = data.total_errors || 0;
    
    // Calculate total connections
    let totalConnections = 0;
    if (data.networks) {
        Object.values(data.networks).forEach(network => {
            totalConnections += network.client_connections || 0;
        });
    }
    document.getElementById('total-connections').textContent = totalConnections;
    
    // Update license info
    document.getElementById('license-info').textContent = `License: ${data.license_plan || 'None'}`;
    
    // Update uptime
    if (data.uptime_seconds) {
        const uptime = formatUptime(data.uptime_seconds);
        document.getElementById('uptime-info').textContent = `Uptime: ${uptime}`;
    }
    
    // Update networks table
    updateNetworksTable(data.networks || {});
    
    // Update last updated timestamp
    const now = new Date();
    document.getElementById('last-updated').textContent = `Last updated: ${now.toLocaleTimeString()}`;
    
    // Check for errors and add to log
    checkForErrors(data);
}

/**
 * Update networks table
 * @param {Object} networks - Networks data
 */
function updateNetworksTable(networks) {
    const tableBody = document.getElementById('networks-table-body');
    
    // Clear table
    tableBody.innerHTML = '';
    
    // Check if networks exist
    if (Object.keys(networks).length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="9" class="text-center">No networks found</td>';
        tableBody.appendChild(row);
        return;
    }
    
    // Add networks to table
    Object.entries(networks).forEach(([networkId, network]) => {
        const row = document.createElement('tr');
        
        // Status class
        let statusClass = '';
        switch (network.status) {
            case 'running':
                statusClass = 'text-success';
                break;
            case 'stopped':
                statusClass = 'text-secondary';
                break;
            case 'error':
                statusClass = 'text-danger';
                break;
            case 'starting':
                statusClass = 'text-info';
                break;
            case 'stopping':
                statusClass = 'text-warning';
                break;
        }
        
        // Format last heartbeat
        let heartbeat = 'Never';
        if (network.last_heartbeat) {
            const date = new Date(network.last_heartbeat);
            heartbeat = date.toLocaleTimeString();
        }
        
        // Create action buttons based on status
        let actionButtons = '';
        if (network.status === 'running') {
            actionButtons = `
                <button class="btn btn-sm btn-outline-warning me-1" onclick="restartNetwork('${networkId}')">
                    <i class="bi bi-arrow-repeat"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="stopNetwork('${networkId}')">
                    <i class="bi bi-stop-fill"></i>
                </button>
            `;
        } else if (network.status === 'stopped' || network.status === 'error') {
            actionButtons = `
                <button class="btn btn-sm btn-outline-success" onclick="startNetwork('${networkId}')">
                    <i class="bi bi-play-fill"></i>
                </button>
            `;
        } else {
            // Starting or stopping - show disabled button
            actionButtons = `
                <button class="btn btn-sm btn-outline-secondary" disabled>
                    <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                </button>
            `;
        }
        
        row.innerHTML = `
            <td>
                <a href="#" onclick="showNetworkDetails('${networkId}'); return false;">
                    ${networkId}
                </a>
            </td>
            <td>${network.model_id}</td>
            <td class="${statusClass}">
                <span class="status-indicator status-${network.status}"></span>
                ${capitalizeFirst(network.status)}
            </td>
            <td>${network.host}:${network.port}</td>
            <td>${network.request_count || 0}</td>
            <td>${network.error_count || 0}</td>
            <td>${network.client_connections || 0}</td>
            <td>${heartbeat}</td>
            <td>
                <div class="btn-group" role="group">
                    <button class="btn btn-sm btn-outline-primary me-1" onclick="showNetworkDetails('${networkId}')">
                        <i class="bi bi-info-circle"></i>
                    </button>
                    ${actionButtons}
                </div>
            </td>
        `;
        
        tableBody.appendChild(row);
    });
}

/**
 * Show network details in modal
 * @param {string} networkId - Network ID
 */
function showNetworkDetails(networkId) {
    // Get modal elements
    const modal = new bootstrap.Modal(document.getElementById('network-detail-modal'));
    const modalTitle = document.getElementById('network-detail-title');
    const modalBody = document.getElementById('network-detail-body');
    
    // Set title
    modalTitle.textContent = `Network Details: ${networkId}`;
    
    // Show loading
    modalBody.innerHTML = `
        <div class="d-flex justify-content-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    
    // Show modal
    modal.show();
    
    // Fetch network details
    fetch(`/api/network/${networkId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            const network = data.network;
            
            // Format uptime
            let uptimeText = 'Not available';
            if (network.uptime_seconds) {
                uptimeText = formatUptime(network.uptime_seconds);
            }
            
            // Format last heartbeat
            let heartbeat = 'Never';
            if (network.last_heartbeat) {
                const date = new Date(network.last_heartbeat);
                heartbeat = date.toLocaleString();
            }
            
            // Build details HTML
            let html = `
                <div class="network-detail-section">
                    <h5>Status Information</h5>
                    <div class="row">
                        <div class="col-md-6">
                            <p><strong>Status:</strong> <span class="${getStatusClass(network.status)}">${capitalizeFirst(network.status)}</span></p>
                            <p><strong>Model:</strong> ${network.model_id}</p>
                            <p><strong>Endpoint:</strong> ${network.host}:${network.port}</p>
                        </div>
                        <div class="col-md-6">
                            <p><strong>Uptime:</strong> ${uptimeText}</p>
                            <p><strong>Last Heartbeat:</strong> ${heartbeat}</p>
                            <p><strong>Client Connections:</strong> ${network.client_connections || 0}</p>
                        </div>
                    </div>
                </div>
                
                <div class="network-detail-section">
                    <h5>Performance Metrics</h5>
                    <div class="row">
                        <div class="col-md-6">
                            <p><strong>Total Requests:</strong> ${network.request_count || 0}</p>
                            <p><strong>Error Count:</strong> ${network.error_count || 0}</p>
                        </div>
                        <div class="col-md-6">
                            <p><strong>Error Rate:</strong> ${calculateErrorRate(network.request_count, network.error_count)}%</p>
                        </div>
                    </div>
                </div>
            `;
            
            // Add configuration details if available
            if (network.config) {
                html += `
                    <div class="network-detail-section">
                        <h5>Configuration</h5>
                        <div class="row">
                            <div class="col-md-12">
                                <p><strong>Model Chain Order:</strong> ${network.config.model_chain_order.join(' → ') || 'N/A'}</p>
                                <p><strong>Paths:</strong></p>
                                <pre class="bg-light p-2 rounded">${JSON.stringify(network.config.paths, null, 2)}</pre>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            // Add recent errors if available
            if (network.recent_errors && network.recent_errors.length > 0) {
                html += `
                    <div class="network-detail-section">
                        <h5>Recent Errors</h5>
                        <div class="error-log">
                `;
                
                network.recent_errors.forEach(error => {
                    html += `<div class="error-entry">${error}</div>`;
                });
                
                html += `
                        </div>
                    </div>
                `;
            }
            
            // Set modal body content
            modalBody.innerHTML = html;
        })
        .catch(error => {
            console.error('Error fetching network details:', error);
            modalBody.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>
                    Failed to load network details: ${error.message}
                </div>
            `;
        });
}

/**
 * Start a network
 * @param {string} networkId - Network ID
 */
function startNetwork(networkId) {
    sendNetworkCommand(networkId, 'start');
}

/**
 * Stop a network
 * @param {string} networkId - Network ID
 */
function stopNetwork(networkId) {
    if (confirm(`Are you sure you want to stop network ${networkId}?`)) {
        sendNetworkCommand(networkId, 'stop');
    }
}

/**
 * Restart a network
 * @param {string} networkId - Network ID
 */
function restartNetwork(networkId) {
    if (confirm(`Are you sure you want to restart network ${networkId}?`)) {
        sendNetworkCommand(networkId, 'restart');
    }
}

/**
 * Send network command
 * @param {string} networkId - Network ID
 * @param {string} command - Command (start, stop, restart)
 */
function sendNetworkCommand(networkId, command) {
    // Show loading overlay
    const overlay = document.createElement('div');
    overlay.style.position = 'fixed';
    overlay.style.top = '0';
    overlay.style.left = '0';
    overlay.style.width = '100%';
    overlay.style.height = '100%';
    overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
    overlay.style.display = 'flex';
    overlay.style.justifyContent = 'center';
    overlay.style.alignItems = 'center';
    overlay.style.zIndex = '9999';
    overlay.innerHTML = `
        <div class="bg-white p-4 rounded shadow">
            <div class="d-flex align-items-center">
                <div class="spinner-border me-3" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div>
                    <h5 class="mb-0">${capitalizeFirst(command)}ing network...</h5>
                    <p class="mb-0 text-muted">Please wait</p>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    
    // Send command
    fetch(`/api/control/${command}/${networkId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Show success message
            const successToast = document.createElement('div');
            successToast.className = 'position-fixed bottom-0 end-0 p-3';
            successToast.style.zIndex = '9999';
            successToast.innerHTML = `
                <div class="toast show" role="alert" aria-live="assertive" aria-atomic="true">
                    <div class="toast-header bg-success text-white">
                        <strong class="me-auto">Success</strong>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
                    </div>
                    <div class="toast-body">
                        ${data.message || `Network ${networkId} ${command}ed successfully`}
                    </div>
                </div>
            `;
            document.body.appendChild(successToast);
            
            // Auto-hide toast after 3 seconds
            setTimeout(() => {
                const toast = new bootstrap.Toast(successToast.querySelector('.toast'));
                toast.hide();
                setTimeout(() => successToast.remove(), 500);
            }, 3000);
            
            // Refresh dashboard after a short delay
            setTimeout(refreshDashboard, 1000);
        })
        .catch(error => {
            console.error(`Error ${command}ing network:`, error);
            addErrorToLog('Network Control', `Failed to ${command} network ${networkId}: ${error.message}`);
            
            // Show error message
            alert(`Failed to ${command} network ${networkId}: ${error.message}`);
        })
        .finally(() => {
            // Remove loading overlay
            document.body.removeChild(overlay);
        });
}

/**
 * Check for errors in data and add to log
 * @param {Object} data - Dashboard data
 */
function checkForErrors(data) {
    // Check for network errors
    if (data.networks) {
        Object.entries(data.networks).forEach(([networkId, network]) => {
            if (network.status === 'error') {
                addErrorToLog(networkId, `Network in error state`);
            }
            
            if (network.recent_errors && network.recent_errors.length > 0) {
                network.recent_errors.forEach(error => {
                    addErrorToLog(networkId, error);
                });
            }
        });
    }
}

/**
 * Add error to log
 * @param {string} source - Error source
 * @param {string} message - Error message
 */
function addErrorToLog(source, message) {
    // Add to error log array (max 100 entries)
    const timestamp = new Date().toISOString();
    errorLog.unshift({ timestamp, source, message });
    if (errorLog.length > 100) {
        errorLog.pop();
    }
    
    // Update error log display
    updateErrorLog();
}

/**
 * Update error log display
 */
function updateErrorLog() {
    const logElement = document.getElementById('error-log');
    
    if (errorLog.length === 0) {
        logElement.innerHTML = '<div class="text-center text-muted">No errors to display</div>';
        return;
    }
    
    let html = '';
    errorLog.forEach(error => {
        const date = new Date(error.timestamp);
        html += `
            <div class="error-entry">
                <div class="error-timestamp">
                    ${date.toLocaleString()} - ${error.source}
                </div>
                <div class="error-message">
                    ${error.message}
                </div>
            </div>
        `;
    });
    
    logElement.innerHTML = html;
}

/**
 * Clear error log
 */
function clearErrorLog() {
    errorLog = [];
    updateErrorLog();
}

/**
 * Format uptime seconds into readable string
 * @param {number} seconds - Uptime in seconds
 * @returns {string} Formatted uptime
 */
function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    const parts = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);
    if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);
    
    return parts.join(' ');
}

/**
 * Calculate error rate percentage
 * @param {number} requests - Total requests
 * @param {number} errors - Total errors
 * @returns {string} Error rate percentage
 */
function calculateErrorRate(requests, errors) {
    if (!requests || requests === 0) return '0.00';
    const rate = (errors / requests) * 100;
    return rate.toFixed(2);
}

/**
 * Get status CSS class
 * @param {string} status - Status string
 * @returns {string} CSS class
 */
function getStatusClass(status) {
    switch (status) {
        case 'running': return 'text-success';
        case 'stopped': return 'text-secondary';
        case 'error': return 'text-danger';
        case 'starting': return 'text-info';
        case 'stopping': return 'text-warning';
        default: return '';
    }
}

/**
 * Capitalize first letter of string
 * @param {string} str - Input string
 * @returns {string} Capitalized string
 */
function capitalizeFirst(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}