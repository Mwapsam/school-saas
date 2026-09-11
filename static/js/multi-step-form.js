/**
 * Multi-Step Form Component for Admission Registration
 * Follows SOLID and DRY principles with reusable components
 */

class MultiStepForm {
    constructor(formElement, options = {}) {
        this.form = formElement;
        this.options = {
            showProgressBar: true,
            validateOnStep: true,
            saveProgress: true,
            ...options
        };
        
        this.currentStep = 1;
        this.totalSteps = this.form.querySelectorAll('[data-step]').length;
        this.formData = {};
        this.validators = {};
        this.isSubmitting = false;
        this.submissionSuccessful = false;
        this.init();
    }
    
    init() {
        this.setupSteps();
        this.setupProgressBar();
        this.loadSavedProgress();
        this.bindEvents();
        this.showStep(1);
    }
    
    setupSteps() {
        const steps = this.form.querySelectorAll('[data-step]');
        steps.forEach((step, index) => {
            step.style.display = index === 0 ? 'block' : 'none';
            step.setAttribute('data-step-number', index + 1);
        });
    }
    
    setupProgressBar() {
        if (!this.options.showProgressBar) return;
        
        const progressContainer = this.form.querySelector('.progress-container');
        if (!progressContainer) return;
        
        let progressHTML = '<div class="progress-steps">';
        for (let i = 1; i <= this.totalSteps; i++) {
            const stepName = this.getStepName(i);
            progressHTML += `
                <div class="progress-step" data-step="${i}">
                    <div class="step-circle">
                        <span class="step-number">${i}</span>
                        <i class="fas fa-check step-check" style="display: none;"></i>
                    </div>
                    <span class="step-label">${stepName}</span>
                </div>
            `;
            if (i < this.totalSteps) {
                progressHTML += '<div class="step-connector"></div>';
            }
        }
        progressHTML += '</div>';
        
        progressContainer.innerHTML = progressHTML;
    }
    
    getStepName(stepNumber) {
        const stepNames = {
            1: 'Terms & Conditions',
            2: 'Academic Info',
            3: 'Student Details',
            4: 'Guardian 1',
            5: 'Guardian 2 & Address',
            6: 'Previous School & Health',
            7: 'Documents',
            8: 'Declaration'
        };
        return stepNames[stepNumber] || `Step ${stepNumber}`;
    }
    
    bindEvents() {
        // Navigation buttons
        this.form.addEventListener('click', (e) => {
            if (e.target.matches('[data-action="next"]')) {
                e.preventDefault();
                this.nextStep();
            } else if (e.target.matches('[data-action="prev"]')) {
                e.preventDefault();
                this.prevStep();
            } else if (e.target.matches('[data-action="submit"]')) {
                e.preventDefault();
                this.submitForm();
            }
        });
        
        // Progress step clicks
        this.form.addEventListener('click', (e) => {
            if (e.target.closest('.progress-step')) {
                const step = parseInt(e.target.closest('.progress-step').dataset.step);
                if (step <= this.getHighestAccessibleStep()) {
                    this.showStep(step);
                }
            }
        });
        
        // Auto-save on input change
        if (this.options.saveProgress) {
            this.form.addEventListener('input', this.debounce(() => {
                this.saveProgress();
            }, 1000));
        }
        
        // File upload handling
        this.form.addEventListener('change', (e) => {
            if (e.target.type === 'file') {
                this.handleFileUpload(e.target);
            }
        });
    }
    
    async nextStep() {
        if (this.options.validateOnStep && !await this.validateCurrentStep()) {
            return;
        }
        
        this.saveStepData();
        
        if (this.currentStep < this.totalSteps) {
            this.showStep(this.currentStep + 1);
        }
    }
    
    prevStep() {
        if (this.currentStep > 1) {
            this.showStep(this.currentStep - 1);
        }
    }
    
    showStep(stepNumber) {
        // Hide all steps
        const steps = this.form.querySelectorAll('[data-step]');
        steps.forEach(step => step.style.display = 'none');
        
        // Show current step
        const currentStepElement = this.form.querySelector(`[data-step="${stepNumber}"]`);
        if (currentStepElement) {
            currentStepElement.style.display = 'block';
            this.currentStep = stepNumber;
            this.updateProgressBar();
            this.updateNavigationButtons();
            
            // Trigger step show event
            this.form.dispatchEvent(new CustomEvent('stepShown', {
                detail: { step: stepNumber }
            }));
        }
    }
    
    updateProgressBar() {
        const progressSteps = this.form.querySelectorAll('.progress-step');
        progressSteps.forEach((step, index) => {
            const stepNum = index + 1;
            const circle = step.querySelector('.step-circle');
            const number = step.querySelector('.step-number');
            const check = step.querySelector('.step-check');
            
            if (stepNum < this.currentStep) {
                // Completed step
                circle.classList.add('completed');
                circle.classList.remove('active');
                number.style.display = 'none';
                check.style.display = 'block';
            } else if (stepNum === this.currentStep) {
                // Current step
                circle.classList.add('active');
                circle.classList.remove('completed');
                number.style.display = 'block';
                check.style.display = 'none';
            } else {
                // Future step
                circle.classList.remove('completed', 'active');
                number.style.display = 'block';
                check.style.display = 'none';
            }
        });
    }
    
    updateNavigationButtons() {
        const prevBtn = this.form.querySelector('[data-action="prev"]');
        const nextBtn = this.form.querySelector('[data-action="next"]');
        const submitBtn = this.form.querySelector('[data-action="submit"]');
        
        if (prevBtn) {
            prevBtn.style.display = this.currentStep === 1 ? 'none' : 'inline-block';
        }
        
        if (this.currentStep === this.totalSteps) {
            if (nextBtn) nextBtn.style.display = 'none';
            if (submitBtn) submitBtn.style.display = 'inline-block';
        } else {
            if (nextBtn) nextBtn.style.display = 'inline-block';
            if (submitBtn) submitBtn.style.display = 'none';
        }
    }
    
    async validateCurrentStep() {
        const currentStepElement = this.form.querySelector(`[data-step="${this.currentStep}"]`);
        const inputs = currentStepElement.querySelectorAll('input, select, textarea');
        let isValid = true;
        
        // Clear previous errors
        currentStepElement.querySelectorAll('.error-message').forEach(el => el.remove());
        currentStepElement.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        
        for (const input of inputs) {
            if (!this.validateField(input)) {
                isValid = false;
            }
        }
        
        // Custom step validation
        const stepValidator = this.validators[this.currentStep];
        if (stepValidator) {
            const customValidation = await stepValidator(currentStepElement);
            if (!customValidation.isValid) {
                this.showError(customValidation.message);
                isValid = false;
            }
        }
        
        return isValid;
    }
    
    validateField(field) {
        const rules = this.getValidationRules(field);
        
        for (const rule of rules) {
            if (!rule.test(field.value)) {
                this.showFieldError(field, rule.message);
                return false;
            }
        }
        
        return true;
    }
    
    getValidationRules(field) {
        const rules = [];
        
        // Required validation
        if (field.required) {
            rules.push({
                test: (value) => value.trim() !== '',
                message: 'This field is required'
            });
        }
        
        // Email validation
        if (field.type === 'email') {
            rules.push({
                test: (value) => !value || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
                message: 'Please enter a valid email address'
            });
        }
        
        // Phone validation
        if (field.dataset.validation === 'phone') {
            rules.push({
                test: (value) => !value || /^[\d\s\-\+\(\)]+$/.test(value),
                message: 'Please enter a valid phone number'
            });
        }
        
        // Date validation
        if (field.type === 'date') {
            rules.push({
                test: (value) => !value || !isNaN(Date.parse(value)),
                message: 'Please enter a valid date'
            });
        }
        
        // File validation
        if (field.type === 'file') {
            const maxSize = parseInt(field.dataset.maxSize) || 5 * 1024 * 1024; // 5MB default
            const allowedTypes = field.dataset.allowedTypes ? field.dataset.allowedTypes.split(',') : [];
            
            rules.push({
                test: (value) => {
                    if (!field.files.length) return !field.required;
                    
                    const file = field.files[0];
                    
                    // Size check
                    if (file.size > maxSize) {
                        return false;
                    }
                    
                    // Type check
                    if (allowedTypes.length && !allowedTypes.some(type => 
                        file.type.includes(type) || file.name.toLowerCase().includes(type))) {
                        return false;
                    }
                    
                    return true;
                },
                message: 'File size or type not allowed'
            });
        }
        
        return rules;
    }
    
    showFieldError(field, message) {
        field.classList.add('is-invalid');
        
        const errorElement = document.createElement('div');
        errorElement.className = 'error-message text-danger small mt-1';
        errorElement.textContent = message;
        
        field.parentNode.appendChild(errorElement);
    }
    
    showError(message) {
        UIHelpers.showAlert(message, 'danger');
    }
    
    saveStepData() {
        const currentStepElement = this.form.querySelector(`[data-step="${this.currentStep}"]`);
        const inputs = currentStepElement.querySelectorAll('input, select, textarea');
        
        inputs.forEach(input => {
            if (input.type === 'file') {
                // Handle file separately
                return;
            }
            
            if (input.type === 'checkbox') {
                // Always store checkbox state (checked or unchecked)
                this.formData[input.name] = input.checked ? input.value : '';
            } else if (input.type === 'radio') {
                if (input.checked) {
                    this.formData[input.name] = input.value;
                }
            } else {
                this.formData[input.name] = input.value;
            }
        });
    }
    
    saveProgress() {
        if (this.options.saveProgress) {
            const progressData = {
                currentStep: this.currentStep,
                formData: this.formData,
                timestamp: Date.now()
            };
            
            localStorage.setItem('admission_form_progress', JSON.stringify(progressData));
        }
    }
    
    loadSavedProgress() {
        if (!this.options.saveProgress) return;
        
        const saved = localStorage.getItem('admission_form_progress');
        if (saved) {
            try {
                const progressData = JSON.parse(saved);
                
                // Check if data is not too old (24 hours)
                const maxAge = 24 * 60 * 60 * 1000;
                if (Date.now() - progressData.timestamp < maxAge) {
                    this.formData = progressData.formData;
                    this.populateForm();
                    
                    // Ask user if they want to continue from where they left off
                    if (confirm('We found your previous progress. Would you like to continue from where you left off?')) {
                        this.showStep(progressData.currentStep);
                    }
                }
            } catch (e) {
                // Invalid saved data
                localStorage.removeItem('admission_form_progress');
            }
        }
    }
    
    populateForm() {
        Object.keys(this.formData).forEach(name => {
            const field = this.form.querySelector(`[name="${name}"]`);
            if (field && this.formData[name]) {
                if (field.type === 'checkbox' || field.type === 'radio') {
                    field.checked = field.value === this.formData[name];
                } else {
                    field.value = this.formData[name];
                }
            }
        });
    }
    
    getHighestAccessibleStep() {
        // Users can navigate back to any previously visited step
        // but can't jump forward without validation
        return Math.max(this.currentStep, Object.keys(this.formData).length ? this.currentStep : 1);
    }
    
    async handleFileUpload(fileInput) {
        if (!fileInput.files.length) return;
        
        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('file', file);
        formData.append('field_name', fileInput.name);
        
        try {
            // Show loading state
            const loadingElement = this.createLoadingElement();
            fileInput.parentNode.appendChild(loadingElement);
            
            const response = await fetch('/api/upload/document/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken(),
                },
                body: formData
            });
            
            if (response.ok) {
                const data = await response.json();
                this.handleFileUploadSuccess(fileInput, data);
            } else {
                throw new Error('Upload failed');
            }
        } catch (error) {
            this.handleFileUploadError(fileInput, error);
        } finally {
            // Remove loading state
            const loadingElement = fileInput.parentNode.querySelector('.file-upload-loading');
            if (loadingElement) loadingElement.remove();
        }
    }
    
    handleFileUploadSuccess(fileInput, data) {
        // Create preview element
        const preview = this.createFilePreview(data);
        fileInput.parentNode.appendChild(preview);
        
        // Store file data
        this.formData[fileInput.name + '_file'] = data;
        
        UIHelpers.showAlert('File uploaded successfully', 'success');
    }
    
    handleFileUploadError(fileInput, error) {
        this.showFieldError(fileInput, 'Failed to upload file. Please try again.');
    }
    
    createLoadingElement() {
        const element = document.createElement('div');
        element.className = 'file-upload-loading text-center py-2';
        element.innerHTML = '<div class="loading-spinner d-inline-block"></div> <span>Uploading...</span>';
        return element;
    }
    
    createFilePreview(fileData) {
        const preview = document.createElement('div');
        preview.className = 'file-preview card mt-2';
        preview.innerHTML = `
            <div class="card-body p-2">
                <div class="d-flex align-items-center">
                    <i class="fas fa-file-alt me-2"></i>
                    <div class="flex-grow-1">
                        <small class="fw-semibold">${fileData.name}</small>
                        <br>
                        <small class="text-muted">${this.formatFileSize(fileData.size)}</small>
                    </div>
                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('.file-preview').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        `;
        return preview;
    }
    
    formatFileSize(bytes) {
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        if (bytes === 0) return '0 Byte';
        const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
        return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
    }
    
    async submitForm() {
        // Prevent double submission - check if already submitting
        if (this.isSubmitting) {
            console.log('Form is already being submitted, ignoring duplicate request');
            return;
        }
        
        this.isSubmitting = true;
        
        // Safety mechanism: Reset form after 60 seconds if something goes wrong
        const safetyTimeout = setTimeout(() => {
            console.warn('Form submission safety timeout reached - resetting form state');
            this.isSubmitting = false;
            this.submissionSuccessful = false;
            
            const allButtons = this.form.querySelectorAll('button, input[type="submit"]');
            allButtons.forEach(btn => {
                btn.disabled = false;
                btn.classList.remove('submitting');
            });
            
            const submitButton = this.form.querySelector('[data-action="submit"]');
            if (submitButton) {
                submitButton.innerHTML = '<i class="fas fa-paper-plane me-2"></i>Submit Application';
            }
            
            this.showError('Submission took too long. Please try again or contact support if the problem persists.');
        }, 60000); // 60 seconds
        
        // Validate all steps
        for (let step = 1; step <= this.totalSteps; step++) {
            this.currentStep = step;
            if (!await this.validateCurrentStep()) {
                this.showStep(step);
                this.isSubmitting = false; // Reset flag on validation failure
                return;
            }
        }
        
        // Collect all form data
        this.saveStepData();
        
        try {
            console.log('Starting form submission...');
            
            const submitButton = this.form.querySelector('[data-action="submit"]');
            const allButtons = this.form.querySelectorAll('button, input[type="submit"]');
            const originalText = submitButton.innerHTML;
            
            // Disable all buttons to prevent any interaction
            allButtons.forEach(btn => {
                btn.disabled = true;
                btn.classList.add('submitting');
            });
            // Use a simple text spinner if CSS spinner not available
            submitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Submitting...';
            
            // Capture current step data before submission
            this.saveStepData();
            
            console.log('Making API request...');
            const response = await this.submitFormData();
            console.log('API response received:', response);
            
            if (response && response.success) {
                this.onSubmissionSuccess(response);
            } else {
                const errorMsg = (response && response.error) || 'Submission failed - no success status';
                console.error('Submission failed:', errorMsg, response);
                throw new Error(errorMsg);
            }
        } catch (error) {
            console.error('Submission error caught:', error);
            this.onSubmissionError(error);
        } finally {
            // Clear the safety timeout
            clearTimeout(safetyTimeout);
            
            // Always reset the submitting flag in case of error
            if (!this.submissionSuccessful) {
                this.isSubmitting = false;
                console.log('Submission flag reset due to failure or incomplete submission');
            }
        }
    }
    
    async submitFormData() {
        console.log('Preparing form data for submission...');
        const formData = new FormData(this.form);
        
        // Add current step and action
        formData.append('step', String(this.totalSteps));
        formData.append('action', 'submit');
        
        // Add double submission prevention token
        const submissionToken = this.generateSubmissionToken();
        formData.append('submission_token', submissionToken);
        
        console.log('Form action URL:', this.form.action);
        console.log('CSRF Token:', this.getCSRFToken());
        console.log('Form data entries:', Array.from(formData.entries()).map(([k, v]) => [k, typeof v === 'object' ? '[File]' : v]));
        
        // Add all form data including files
        Object.keys(this.formData).forEach(key => {
            // For checkboxes, we want to include even empty values (unchecked state)
            const isCheckbox = this.form.querySelector(`[name="${key}"][type="checkbox"]`);
            
            if ((this.formData[key] || isCheckbox) && !formData.has(key)) {
                if (key.endsWith('_file')) {
                    // Skip file data, it should be handled by form serialization
                    return;
                } else {
                    formData.append(key, this.formData[key] || '');
                }
            }
        });
        
        try {
            // Add timeout to prevent infinite loading
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
            
            const response = await fetch(this.form.action, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken(),
                },
                body: formData,
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                
                // Try to get more detailed error from response
                try {
                    const errorText = await response.text();
                    if (errorText) {
                        // Check if it's JSON
                        try {
                            const errorJson = JSON.parse(errorText);
                            if (errorJson.error) {
                                errorMessage = errorJson.error;
                            }
                        } catch (e) {
                            // Not JSON, use first 200 chars of text
                            errorMessage = errorText.substring(0, 200);
                        }
                    }
                } catch (e) {
                    // Failed to read response text, use default message
                }
                
                throw new Error(errorMessage);
            }
            
            // Parse JSON response
            let jsonResponse;
            try {
                const responseText = await response.text();
                jsonResponse = JSON.parse(responseText);
            } catch (e) {
                throw new Error('Server returned invalid JSON response');
            }
            
            return jsonResponse;
            
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error('Request timed out. Please check your connection and try again.');
            }
            throw error;
        }
    }
    
    onSubmissionSuccess(response) {
        // Mark submission as successful to prevent flag reset
        this.submissionSuccessful = true;
        
        // Clear saved progress
        localStorage.removeItem('admission_form_progress');
        
        // Show success message
        if (typeof UIHelpers !== 'undefined') {
            UIHelpers.showAlert('Application submitted successfully!', 'success');
        } else {
            alert('Application submitted successfully!');
        }
        
        // Redirect to success page
        if (response.redirect) {
            setTimeout(() => {
                window.location.href = response.redirect;
            }, 2000);
        }
    }
    
    onSubmissionError(error) {
        console.error('Submission error:', error);
        
        // Show user-friendly error message
        let errorMessage = 'Failed to submit application. Please try again.';
        if (error && error.message) {
            if (error.message.includes('timeout') || error.message.includes('timed out')) {
                errorMessage = 'Request timed out. Please check your internet connection and try again.';
            } else if (error.message.includes('network') || error.message.includes('fetch')) {
                errorMessage = 'Network error. Please check your internet connection and try again.';
            } else if (error.message.length < 200) {
                errorMessage = error.message;
            }
        }
        
        this.showError(errorMessage);
        
        // Re-enable all buttons and reset their state
        const allButtons = this.form.querySelectorAll('button, input[type="submit"]');
        allButtons.forEach(btn => {
            btn.disabled = false;
            btn.classList.remove('submitting');
        });
        
        const submitButton = this.form.querySelector('[data-action="submit"]');
        if (submitButton) {
            submitButton.innerHTML = '<i class="fas fa-paper-plane me-2"></i>Submit Application';
        }
        
        // Reset submission flag
        this.isSubmitting = false;
    }
    
    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }
    
    generateSubmissionToken() {
        // Generate a unique token for this submission to prevent double submission
        const timestamp = Date.now();
        const random = Math.random().toString(36).substring(2, 15);
        return `${timestamp}_${random}`;
    }
    
    debounce(func, wait) {
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
    
    // Public API methods
    addValidator(step, validator) {
        this.validators[step] = validator;
    }
    
    goToStep(step) {
        if (step >= 1 && step <= this.totalSteps) {
            this.showStep(step);
        }
    }
    
    getFormData() {
        return { ...this.formData };
    }
    
    setFormData(data) {
        this.formData = { ...this.formData, ...data };
        this.populateForm();
    }
}

// Export for use
window.MultiStepForm = MultiStepForm;