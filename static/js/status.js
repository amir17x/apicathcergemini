// Status page functionality for Gmail & Gemini API Creator Bot

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Feather Icons
    feather.replace();
    
    // Load account data
    loadAccountData();
    
    // Set up refresh button
    document.getElementById('refreshButton').addEventListener('click', function() {
        loadAccountData();
    });
    
    // Auto-refresh every 30 seconds
    setInterval(loadAccountData, 30000);
});

/**
 * Load account data from the API
 */
function loadAccountData() {
    fetch('/api/accounts')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(accounts => {
            displayAccounts(accounts);
        })
        .catch(error => {
            console.error('Error fetching account data:', error);
            const tableBody = document.getElementById('accounts-table-body');
            tableBody.innerHTML = `
                <tr>
                    <td colspan="4" class="text-center text-danger">
                        <i data-feather="alert-triangle" class="me-2"></i>
                        Error loading account data. Please try again.
                    </td>
                </tr>
            `;
            feather.replace();
        });
}

/**
 * Display accounts in the table
 */
function displayAccounts(accounts) {
    const tableBody = document.getElementById('accounts-table-body');
    const noAccountsDiv = document.getElementById('no-accounts');
    
    if (accounts.length === 0) {
        tableBody.innerHTML = '';
        noAccountsDiv.classList.remove('d-none');
        return;
    }
    
    noAccountsDiv.classList.add('d-none');
    
    let html = '';
    accounts.forEach(account => {
        const statusBadge = getStatusBadge(account.status);
        const formattedDate = formatDateTime(account.created_at);
        
        html += `
            <tr>
                <td>${account.gmail}</td>
                <td>${statusBadge}</td>
                <td>
                    ${account.api_key ? 
                        `<div class="api-key">
                            <span class="truncate">${account.api_key}</span>
                            <span class="copy-btn" onclick="copyToClipboard('${account.api_key}')">
                                <i data-feather="copy" style="width: 14px; height: 14px;"></i>
                            </span>
                        </div>` : 
                        '<span class="text-muted">Not available</span>'
                    }
                </td>
                <td>${formattedDate}</td>
            </tr>
        `;
    });
    
    tableBody.innerHTML = html;
    feather.replace();
}

/**
 * Get appropriate status badge based on status
 */
function getStatusBadge(status) {
    let badgeClass = 'bg-secondary';
    let icon = 'help-circle';
    
    switch(status) {
        case 'creating_gmail':
            badgeClass = 'bg-warning text-dark';
            icon = 'mail';
            break;
        case 'generating_api_key':
            badgeClass = 'bg-info text-dark';
            icon = 'key';
            break;
        case 'completed':
            badgeClass = 'bg-success';
            icon = 'check-circle';
            break;
        case 'gmail_creation_failed':
        case 'api_key_generation_failed':
        case 'error':
            badgeClass = 'bg-danger';
            icon = 'alert-circle';
            break;
        case 'pending':
            badgeClass = 'bg-secondary';
            icon = 'clock';
            break;
    }
    
    return `
        <span class="badge ${badgeClass}">
            <i data-feather="${icon}" style="width: 14px; height: 14px;"></i>
            ${status}
        </span>
    `;
}

/**
 * Format datetime for display
 */
function formatDateTime(dateTimeStr) {
    if (!dateTimeStr) return 'N/A';
    
    const date = new Date(dateTimeStr);
    return date.toLocaleString();
}

/**
 * Copy text to clipboard
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        // Show temporary toast or notification
        showToast('API key copied to clipboard!');
    }).catch(err => {
        console.error('Could not copy text: ', err);
    });
}

/**
 * Show a temporary toast notification
 */
function showToast(message) {
    // Create toast container if it doesn't exist
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-white bg-success border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    <i data-feather="check-circle" class="me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    toastContainer.innerHTML += toastHtml;
    
    // Initialize and show toast
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
    toast.show();
    
    // Replace feather icons after creating the toast
    feather.replace();
    
    // Remove toast after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
}
