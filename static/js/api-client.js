/**
 * API Client for Pinewood School Management System
 * Provides standardized interface to DRF APIs across the application
 */

class APIClient {
    constructor() {
        this.baseURL = '/api/v1';
        this.csrfToken = this.getCSRFToken();
        
        // Default headers for all requests
        this.headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken,
        };
    }

    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: this.headers,
            ...options
        };

        try {
            const response = await fetch(url, config);
            
            // Handle different response types
            const contentType = response.headers.get('content-type');
            let data;
            
            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                data = await response.text();
            }

            if (!response.ok) {
                throw new APIError(data.detail || `HTTP ${response.status}`, response.status, data);
            }

            return data;
        } catch (error) {
            if (error instanceof APIError) {
                throw error;
            }
            throw new APIError('Network error', 0, error);
        }
    }

    // Generic CRUD methods
    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        return this.request(url, { method: 'GET' });
    }

    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async patch(endpoint, data) {
        return this.request(endpoint, {
            method: 'PATCH',
            body: JSON.stringify(data)
        });
    }

    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    // Student API methods
    students = {
        list: (params = {}) => this.get('/students/', params),
        get: (id) => this.get(`/students/${id}/`),
        create: (data) => this.post('/students/', data),
        update: (id, data) => this.put(`/students/${id}/`, data),
        partialUpdate: (id, data) => this.patch(`/students/${id}/`, data),
        delete: (id) => this.delete(`/students/${id}/`),
        bulkCreate: (data) => this.post('/students/bulk_create/', data),
        bulkUpdate: (data) => this.post('/students/bulk_update/', data),
        search: (params) => this.get('/students/search/', params),
        byBatch: (batchId, params = {}) => this.get(`/students/by_batch/${batchId}/`, params)
    };

    // Course API methods
    courses = {
        list: (params = {}) => this.get('/courses/', params),
        get: (id) => this.get(`/courses/${id}/`),
        create: (data) => this.post('/courses/', data),
        update: (id, data) => this.put(`/courses/${id}/`, data),
        delete: (id) => this.delete(`/courses/${id}/`),
        search: (params) => this.get('/courses/search/', params)
    };

    // Batch API methods
    batches = {
        list: (params = {}) => this.get('/batches/', params),
        get: (id) => this.get(`/batches/${id}/`),
        create: (data) => this.post('/batches/', data),
        update: (id, data) => this.put(`/batches/${id}/`, data),
        delete: (id) => this.delete(`/batches/${id}/`),
        search: (params) => this.get('/batches/search/', params),
        students: (id, params = {}) => this.get(`/batches/${id}/students/`, params)
    };

    // Admission API methods
    admissions = {
        list: (params = {}) => this.get('/admissions/', params),
        get: (id) => this.get(`/admissions/${id}/`),
        create: (data) => this.post('/admissions/', data),
        update: (id, data) => this.put(`/admissions/${id}/`, data),
        approve: (id, data = {}) => this.post(`/admissions/${id}/approve/`, data),
        reject: (id, data) => this.post(`/admissions/${id}/reject/`, data),
        search: (params) => this.get('/admissions/search/', params),
        statistics: () => this.get('/admissions/statistics/')
    };

    // Subject API methods
    subjects = {
        list: (params = {}) => this.get('/subjects/', params),
        get: (id) => this.get(`/subjects/${id}/`),
        create: (data) => this.post('/subjects/', data),
        update: (id, data) => this.put(`/subjects/${id}/`, data),
        delete: (id) => this.delete(`/subjects/${id}/`),
        byBatch: (batchId) => this.get(`/subjects/by_batch/${batchId}/`)
    };

    // User API methods
    users = {
        list: (params = {}) => this.get('/users/', params),
        get: (id) => this.get(`/users/${id}/`),
        create: (data) => this.post('/users/', data),
        update: (id, data) => this.patch(`/users/${id}/`, data),
        delete: (id) => this.delete(`/users/${id}/`),
        profile: () => this.get('/users/profile/'),
        changePassword: (data) => this.post('/users/change_password/', data)
    };
}

// Custom error class for API errors
class APIError extends Error {
    constructor(message, status, details) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.details = details;
    }
}

// Utility functions for common UI operations
class UIHelpers {
    static showAlert(message, type = 'info', duration = 5000) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.getElementById('main-content');
        if (container) {
            container.insertBefore(alertDiv, container.firstChild);
            
            if (duration > 0) {
                setTimeout(() => {
                    if (alertDiv.parentNode) {
                        alertDiv.remove();
                    }
                }, duration);
            }
        }
    }

    static showLoading(element, show = true) {
        if (show) {
            element.classList.add('htmx-request');
            element.disabled = true;
        } else {
            element.classList.remove('htmx-request');
            element.disabled = false;
        }
    }

    static formatDate(dateString) {
        return new Date(dateString).toLocaleDateString();
    }

    static formatDateTime(dateString) {
        return new Date(dateString).toLocaleString();
    }

    static handleAPIError(error, defaultMessage = 'An error occurred') {
        console.error('API Error:', error);
        
        let message = defaultMessage;
        if (error instanceof APIError) {
            if (error.status === 400 && error.details) {
                // Handle validation errors
                const errors = Object.values(error.details).flat();
                message = errors.join(', ');
            } else if (error.message) {
                message = error.message;
            }
        }
        
        this.showAlert(message, 'danger');
    }
}

// Pagination helper
class PaginationHelper {
    constructor(container, onPageChange) {
        this.container = container;
        this.onPageChange = onPageChange;
    }

    render(paginationData) {
        if (!paginationData || !this.container) return;

        const { count, next, previous, results } = paginationData;
        const currentPage = this.extractPageNumber(window.location.href) || 1;
        const totalPages = Math.ceil(count / results.length);

        let paginationHTML = '<nav><ul class="pagination pagination-sm justify-content-center">';
        
        // Previous button
        if (previous) {
            const prevPage = this.extractPageNumber(previous);
            paginationHTML += `<li class="page-item">
                <a class="page-link" href="#" data-page="${prevPage}">Previous</a>
            </li>`;
        } else {
            paginationHTML += '<li class="page-item disabled"><span class="page-link">Previous</span></li>';
        }

        // Page numbers (simplified - show current, prev, next)
        const startPage = Math.max(1, currentPage - 2);
        const endPage = Math.min(totalPages, currentPage + 2);

        if (startPage > 1) {
            paginationHTML += '<li class="page-item"><a class="page-link" href="#" data-page="1">1</a></li>';
            if (startPage > 2) {
                paginationHTML += '<li class="page-item disabled"><span class="page-link">...</span></li>';
            }
        }

        for (let i = startPage; i <= endPage; i++) {
            const activeClass = i === currentPage ? 'active' : '';
            paginationHTML += `<li class="page-item ${activeClass}">
                <a class="page-link" href="#" data-page="${i}">${i}</a>
            </li>`;
        }

        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                paginationHTML += '<li class="page-item disabled"><span class="page-link">...</span></li>';
            }
            paginationHTML += `<li class="page-item"><a class="page-link" href="#" data-page="${totalPages}">${totalPages}</a></li>`;
        }

        // Next button
        if (next) {
            const nextPage = this.extractPageNumber(next);
            paginationHTML += `<li class="page-item">
                <a class="page-link" href="#" data-page="${nextPage}">Next</a>
            </li>`;
        } else {
            paginationHTML += '<li class="page-item disabled"><span class="page-link">Next</span></li>';
        }

        paginationHTML += '</ul></nav>';
        this.container.innerHTML = paginationHTML;

        // Add click handlers
        this.container.querySelectorAll('.page-link[data-page]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = parseInt(e.target.getAttribute('data-page'));
                this.onPageChange(page);
            });
        });
    }

    extractPageNumber(url) {
        const match = url.match(/[?&]page=(\d+)/);
        return match ? parseInt(match[1]) : null;
    }
}

// Initialize global API client
window.api = new APIClient();
window.UIHelpers = UIHelpers;
window.PaginationHelper = PaginationHelper;