/**
 * Academic Management API Client
 * Following Fedena SMS pattern for academic management
 */

class AcademicAPI {
    constructor() {
        this.baseUrl = window.location.origin;
        this.csrfToken = this.getCsrfToken();
    }

    getCsrfToken() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return value;
            }
        }
        return null;
    }

    async makeRequest(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            }
        };

        const config = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers
            }
        };

        try {
            const response = await fetch(url, config);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || `HTTP error! status: ${response.status}`);
            }
            
            return data;
        } catch (error) {
            console.error('API Request failed:', error);
            throw error;
        }
    }

    // Course Management
    async getCourses(searchQuery = '') {
        const params = new URLSearchParams();
        if (searchQuery) params.append('search', searchQuery);
        
        return this.makeRequest(`${this.baseUrl}/api/courses/?${params}`);
    }

    async createCourse(courseData) {
        return this.makeRequest(`${this.baseUrl}/api/courses/`, {
            method: 'POST',
            body: JSON.stringify(courseData)
        });
    }

    async updateCourse(courseId, courseData) {
        return this.makeRequest(`${this.baseUrl}/api/courses/${courseId}/`, {
            method: 'PUT',
            body: JSON.stringify(courseData)
        });
    }

    async deleteCourse(courseId) {
        return this.makeRequest(`${this.baseUrl}/api/courses/${courseId}/`, {
            method: 'DELETE'
        });
    }

    // Subject Management
    async getSubjects(batchId = '', searchQuery = '') {
        const params = new URLSearchParams();
        if (batchId) params.append('batch_id', batchId);
        if (searchQuery) params.append('search', searchQuery);
        
        return this.makeRequest(`${this.baseUrl}/api/subjects/?${params}`);
    }

    async createSubject(subjectData) {
        return this.makeRequest(`${this.baseUrl}/api/subjects/`, {
            method: 'POST',
            body: JSON.stringify(subjectData)
        });
    }

    async updateSubject(subjectId, subjectData) {
        return this.makeRequest(`${this.baseUrl}/api/subjects/${subjectId}/`, {
            method: 'PUT',
            body: JSON.stringify(subjectData)
        });
    }

    async deleteSubject(subjectId) {
        return this.makeRequest(`${this.baseUrl}/api/subjects/${subjectId}/`, {
            method: 'DELETE'
        });
    }

    // Timetable Management
    async getTimetable(batchId, weekdayId = '') {
        const params = new URLSearchParams();
        params.append('batch_id', batchId);
        if (weekdayId) params.append('weekday_id', weekdayId);
        
        return this.makeRequest(`${this.baseUrl}/api/timetable/?${params}`);
    }

    async createTimetableEntry(timetableData) {
        return this.makeRequest(`${this.baseUrl}/api/timetable/`, {
            method: 'POST',
            body: JSON.stringify(timetableData)
        });
    }

    async updateTimetableEntry(entryId, timetableData) {
        return this.makeRequest(`${this.baseUrl}/api/timetable/${entryId}/`, {
            method: 'PUT',
            body: JSON.stringify(timetableData)
        });
    }

    async deleteTimetableEntry(entryId) {
        return this.makeRequest(`${this.baseUrl}/api/timetable/${entryId}/`, {
            method: 'DELETE'
        });
    }

    // Attendance Management
    async getAttendanceSummary(batchId = '', date = '') {
        const params = new URLSearchParams();
        if (batchId) params.append('batch_id', batchId);
        if (date) params.append('date', date);
        
        return this.makeRequest(`${this.baseUrl}/api/attendance/summary/?${params}`);
    }

    async markAttendance(attendanceData) {
        return this.makeRequest(`${this.baseUrl}/api/attendance/`, {
            method: 'POST',
            body: JSON.stringify(attendanceData)
        });
    }

    async updateAttendance(attendanceId, attendanceData) {
        return this.makeRequest(`${this.baseUrl}/api/attendance/${attendanceId}/`, {
            method: 'PUT',
            body: JSON.stringify(attendanceData)
        });
    }

    async deleteAttendance(attendanceId) {
        return this.makeRequest(`${this.baseUrl}/api/attendance/${attendanceId}/`, {
            method: 'DELETE'
        });
    }

    async bulkMarkAttendance(bulkData) {
        return this.makeRequest(`${this.baseUrl}/api/attendance/bulk/`, {
            method: 'POST',
            body: JSON.stringify(bulkData)
        });
    }

    // Academic Year Management
    async getAcademicYears(searchQuery = '') {
        const params = new URLSearchParams();
        if (searchQuery) params.append('search', searchQuery);
        
        return this.makeRequest(`${this.baseUrl}/api/academic-years/?${params}`);
    }

    async createAcademicYear(yearData) {
        return this.makeRequest(`${this.baseUrl}/api/academic-years/`, {
            method: 'POST',
            body: JSON.stringify(yearData)
        });
    }

    async updateAcademicYear(yearId, yearData) {
        return this.makeRequest(`${this.baseUrl}/api/academic-years/${yearId}/`, {
            method: 'PUT',
            body: JSON.stringify(yearData)
        });
    }

    async deleteAcademicYear(yearId) {
        return this.makeRequest(`${this.baseUrl}/api/academic-years/${yearId}/`, {
            method: 'DELETE'
        });
    }

    // Utility Methods
    async getBatchStudents(batchId) {
        return this.makeRequest(`${this.baseUrl}/api/batches/${batchId}/students/`);
    }

    async searchStudents(query) {
        return this.makeRequest(`${this.baseUrl}/api/students/search/?q=${encodeURIComponent(query)}`);
    }
}

// Global instance
window.academicAPI = new AcademicAPI();

// Utility functions for common operations
class AcademicUtils {
    static showToast(message, type = 'success') {
        // Create toast notification (Bootstrap compatible)
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
        toast.style.zIndex = '9999';
        toast.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, 5000);
    }

    static showError(error) {
        const message = error.message || 'An error occurred';
        this.showToast(message, 'danger');
    }

    static showSuccess(message) {
        this.showToast(message, 'success');
    }

    static formatDate(dateString) {
        if (!dateString) return '';
        return new Date(dateString).toLocaleDateString();
    }

    static formatTime(timeString) {
        if (!timeString) return '';
        return new Date(`1970-01-01T${timeString}`).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    static validateForm(formElement) {
        const requiredFields = formElement.querySelectorAll('[required]');
        let isValid = true;
        let firstInvalidField = null;

        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                field.classList.add('is-invalid');
                if (!firstInvalidField) {
                    firstInvalidField = field;
                }
                isValid = false;
            } else {
                field.classList.remove('is-invalid');
            }
        });

        if (!isValid && firstInvalidField) {
            firstInvalidField.focus();
        }

        return isValid;
    }

    static setLoadingState(button, loading = true) {
        const spinner = button.querySelector('.loading-spinner');
        const text = button.querySelector('[id$="ButtonText"]');
        
        if (loading) {
            button.disabled = true;
            if (spinner) spinner.classList.remove('d-none');
            if (text) text.classList.add('d-none');
        } else {
            button.disabled = false;
            if (spinner) spinner.classList.add('d-none');
            if (text) text.classList.remove('d-none');
        }
    }

    static async handleFormSubmission(formElement, submitHandler) {
        const submitButton = formElement.querySelector('button[type="submit"]');
        
        try {
            if (!this.validateForm(formElement)) {
                return;
            }

            this.setLoadingState(submitButton, true);
            
            const formData = new FormData(formElement);
            const data = Object.fromEntries(formData.entries());
            
            // Handle checkboxes
            const checkboxes = formElement.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(checkbox => {
                data[checkbox.name] = checkbox.checked;
            });

            await submitHandler(data);
            
        } catch (error) {
            this.showError(error);
        } finally {
            this.setLoadingState(submitButton, false);
        }
    }

    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    static async loadSelectOptions(selectElement, apiCall, valueField = 'id', textField = 'name') {
        try {
            const data = await apiCall();
            const options = Array.isArray(data) ? data : data.results || [];
            
            selectElement.innerHTML = '<option value="">Loading...</option>';
            
            selectElement.innerHTML = options.map(option => 
                `<option value="${option[valueField]}">${option[textField]}</option>`
            ).join('');
            
        } catch (error) {
            selectElement.innerHTML = '<option value="">Error loading options</option>';
            this.showError(error);
        }
    }
}

// Global utilities
window.academicUtils = AcademicUtils;

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('Academic API initialized');
});