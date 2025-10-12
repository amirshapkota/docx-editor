// DOCX Editor JavaScript - Cache Buster: 2025-09-26-16:01
class DocxEditor extends DocxBase {
    constructor() {
        super();
        this.pendingDeleteId = null;
        this.complianceCheckTimeout = null;
        this.lastComplianceCheck = {};
        this.initDeleteModal();
        this.initCommentForm();
        this.initExportButton();
        this.loadDocumentsList();
        
        // Track edited commented paragraphs
        this.editedCommentedParagraphs = [];
    }

    async loadDocumentsList() {
        try {
            const response = await fetch('/editor/api/documents/');
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to load documents');
            }

            this.renderDocumentsList(data);
        } catch (error) {
            console.error('Error loading documents:', error);
            this.showStatus('Error loading documents: ' + error.message, 'error');
        }
    }

    renderDocumentsList(documents) {
        const uploadSection = document.getElementById('upload-section');
        const listContainer = document.createElement('div');
        listContainer.className = 'col-lg-12 mb-6 mb-xl-0 documents-list';
        
        // Create the header and container structure
        listContainer.innerHTML = `
            <small class="fw-medium">Available Documents</small>
            <div class="demo-inline-spacing mt-4">
                <div class="list-group" id="documents-list-group">
                </div>
            </div>
        `;

        const listGroup = listContainer.querySelector('#documents-list-group');

        if (documents.length === 0) {
            listGroup.innerHTML = '<div class="list-group-item list-group-item-action disabled">No documents available for editing</div>';
        } else {
            documents.forEach((doc, index) => {
                const item = document.createElement('a');
                item.href = 'javascript:void(0);';
                item.className = 'list-group-item list-group-item-action';
                item.dataset.id = doc.id;
                
                // Truncate long filenames for better display
                const displayName = doc.filename.length > 50 
                    ? doc.filename.substring(0, 47) + '...' 
                    : doc.filename;
                item.textContent = displayName;
                item.title = doc.filename; // Show full name on hover
                
                // Mark the currently loaded document as active
                if (this.currentDocumentId && doc.id === this.currentDocumentId) {
                    item.classList.add('active');
                }
                
                item.addEventListener('click', (e) => {
                    e.preventDefault();
                    
                    // Check for unsaved changes before switching documents
                    if (this.unsavedChanges && !confirm('You have unsaved changes. Are you sure you want to switch documents?')) {
                        return;
                    }
                    
                    // Remove active class from all items
                    listGroup.querySelectorAll('.list-group-item').forEach(el => {
                        el.classList.remove('active');
                    });
                    
                    // Add active class to clicked item
                    item.classList.add('active');
                    
                    this.loadDocument(doc.id);
                });
                
                listGroup.appendChild(item);
            });
        }

        // Insert the list before the upload area
        uploadSection.insertBefore(listContainer, uploadSection.firstChild);
    }
    
    initDeleteModal() {
        document.getElementById('closeModal').addEventListener('click', () => this.hideDeleteModal());
        document.getElementById('cancelDelete').addEventListener('click', () => this.hideDeleteModal());
        document.getElementById('confirmDelete').addEventListener('click', () => this.confirmDelete());
        
        document.getElementById('deleteModal').addEventListener('click', (e) => {
            if (e.target.id === 'deleteModal') {
                this.hideDeleteModal();
            }
        });
    }

    initCommentForm() {
        const commentForm = document.getElementById('addCommentForm');
        if (!commentForm) return;

        const saveCommentBtn = document.getElementById('saveCommentBtn');
        if (saveCommentBtn) {
            saveCommentBtn.addEventListener('click', async () => {
                const paragraphSelect = document.getElementById('paragraphSelect');
                const authorInput = document.getElementById('authorInput');
                const commentInput = document.getElementById('commentInput');

                if (!paragraphSelect.value) {
                    this.showStatus('Please select a paragraph', 'error');
                    return;
                }

                if (!commentInput.value.trim()) {
                    this.showStatus('Please enter a comment', 'error');
                    return;
                }

                try {
                    const response = await fetch('/editor/api/add_comment/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            document_id: this.currentDocumentId,
                            paragraph_id: parseInt(paragraphSelect.value),
                            author: authorInput.value.trim() || 'Anonymous',
                            text: commentInput.value.trim()
                        })
                    });

                    if (!response.ok) {
                        const errorText = await response.text();
                        console.error('Server response:', response.status, errorText);
                        throw new Error(`Failed to add comment: ${response.status} ${errorText}`);
                    }

                    const data = await response.json();
                    this.comments.push(data);
                    this.renderComments();

                    // Clear form
                    commentInput.value = '';
                    
                    // Highlight the paragraph
                    this.highlightParagraph(parseInt(paragraphSelect.value));
                    
                    // Show appropriate status message
                    if (data.docx_success) {
                        this.showStatus('Comment added successfully', 'success');
                    } else {
                        this.showStatus('Comment saved (DOCX update failed: ' + data.docx_error + ')', 'warning');
                    }
                } catch (error) {
                    console.error('Error adding comment:', error);
                    this.showStatus('Error adding comment: ' + error.message, 'error');
                }
            });
        }
    }

    initExportButton() {
        const exportBtn = document.getElementById('exportBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', async () => {
                if (!this.currentDocumentId) return;

                try {
                    this.showStatus('Exporting document...', 'info');
                    
                    // Always sync with database to ensure exported version reflects current edits
                    const response = await fetch(`/editor/api/document/${this.currentDocumentId}/export/?sync=true`, {
                        method: 'GET'
                    });

                    if (!response.ok) {
                        throw new Error('Export failed');
                    }

                    // Get the filename from Content-Disposition header
                    const contentDisposition = response.headers.get('Content-Disposition');
                    let filename = 'document.docx';
                    if (contentDisposition) {
                        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
                        if (filenameMatch && filenameMatch[1]) {
                            filename = filenameMatch[1].replace(/['"]/g, '');
                        }
                    }

                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);

                    this.showStatus('Document exported successfully', 'success');
                } catch (error) {
                    console.error('Export error:', error);
                    this.showStatus('Error exporting document: ' + error.message, 'error');
                }
            });
        }
    }

    createParagraphWrapper(para) {
        const wrapper = super.createParagraphWrapper(para);
        
        // Make paragraph content editable
        const content = wrapper.querySelector('.paragraph-content');
        content.contentEditable = true;
        
        content.addEventListener('input', (e) => {
            this.unsavedChanges = true;
            this.scheduleAutoSave(para.id, content.textContent);
            this.scheduleComplianceCheck(para.id, content.textContent);
        });
        
        content.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.insertParagraphAfter(para.id);
            } else if (e.key === 'Backspace' && content.textContent === '' && this.paragraphs.length > 1) {
                e.preventDefault();
                this.showDeleteModal(para.id);
            } else if (e.key === 'ArrowDown' && this.isAtEndOfParagraph(content)) {
                // If at end of paragraph and pressing down arrow, check if we need a new paragraph
                const nextParagraph = this.getNextParagraph(para.id);
                if (!nextParagraph) {
                    e.preventDefault();
                    this.insertParagraphAfter(para.id);
                }
            }
        });
        
        // Add double-click to insert paragraph after
        content.addEventListener('dblclick', (e) => {
            if (e.detail === 2) { // Ensure it's a real double-click
                const selection = window.getSelection();
                const range = selection.getRangeAt(0);
                const atEnd = range.endOffset === content.textContent.length;
                
                if (atEnd) {
                    this.insertParagraphAfter(para.id);
                }
            }
        });
        
        // Add comment button
        const actions = document.createElement('div');
        actions.className = 'paragraph-actions';
        
        // Delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn-small btn-danger';
        deleteBtn.innerHTML = '&times;';
        deleteBtn.title = 'Delete paragraph';
        deleteBtn.addEventListener('click', () => this.showDeleteModal(para.id));
        actions.appendChild(deleteBtn);
        
        // Duplicate button
        const duplicateBtn = document.createElement('button');
        duplicateBtn.className = 'btn-small btn-warning';
        duplicateBtn.innerHTML = '&#9783;';
        duplicateBtn.title = 'Duplicate paragraph';
        duplicateBtn.addEventListener('click', () => this.duplicateParagraph(para.id));
        actions.appendChild(duplicateBtn);
        
        // Comment button
        const commentBtn = document.createElement('button');
        commentBtn.className = 'btn-small btn-primary';
        commentBtn.innerHTML = '💬';
        commentBtn.title = 'Add comment';
        commentBtn.addEventListener('click', () => {
            const select = document.getElementById('paragraphSelect');
            select.value = para.id;
            this.highlightParagraph(para.id);
            document.getElementById('commentInput').focus();
        });
        actions.appendChild(commentBtn);
        
        wrapper.appendChild(actions);
        
        // Click handler for highlighting
        content.addEventListener('click', () => {
            const select = document.getElementById('paragraphSelect');
            select.value = para.id;
            this.highlightParagraph(para.id);
        });
        
        return wrapper;
    }
    
    scheduleComplianceCheck(paragraphId, text) {
        // Clear previous timeout
        if (this.complianceCheckTimeout) {
            clearTimeout(this.complianceCheckTimeout);
        }
        
        // Only check if there are comments for this paragraph
        const paragraphComments = this.comments.filter(c => c.paragraph_id === paragraphId);
        if (paragraphComments.length === 0) {
            console.log(`No comments for paragraph ${paragraphId}, clearing compliance status`);
            this.clearComplianceStatus(paragraphId);
            return;
        }
        
        console.log(`Scheduling compliance check for paragraph ${paragraphId} with ${paragraphComments.length} comments`);
        
        // Debounced ML compliance check (wait for user to stop typing)
        this.complianceCheckTimeout = setTimeout(async () => {
            try {
                await this.checkComplianceRealTime(paragraphId, text);
            } catch (error) {
                console.error('Real-time compliance check error:', error);
                this.showComplianceStatus(paragraphId, 'error', 0.0, 'Error checking compliance');
            }
        }, 800); // Wait 800ms after user stops typing
    }

    async checkComplianceRealTime(paragraphId, currentText) {
        if (!this.currentDocumentId) {
            console.log('No document ID available for compliance check');
            return;
        }
        
        // Debug logging
        console.log('Checking compliance for:', {
            document_id: this.currentDocumentId,
            paragraph_id: paragraphId,
            current_text: currentText.substring(0, 50) + '...'
        });
        
        try {
            // Show checking status
            this.showComplianceStatus(paragraphId, 'checking', 0.0, 'Checking compliance...');
            
            const response = await fetch('/editor/api/ml/check-compliance-realtime/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    document_id: this.currentDocumentId,
                    paragraph_id: paragraphId,
                    current_text: currentText
                })
            });

            console.log('API response status:', response.status);
            console.log('API response headers:', Object.fromEntries(response.headers.entries()));

            if (!response.ok) {
                const errorText = await response.text();
                console.error('API error response:', errorText);
                throw new Error(`API returned ${response.status}: ${errorText}`);
            }

            const data = await response.json();
            console.log('API response data:', data);
            
            // Store latest compliance result
            this.lastComplianceCheck[paragraphId] = data;
            
            // Collect constraint violations for display
            let allConstraintViolations = [];
            if (data.compliance_results) {
                for (const result of data.compliance_results) {
                    if (result.constraint_validation && result.constraint_validation.violations) {
                        allConstraintViolations.push(...result.constraint_validation.violations);
                    }
                }
            }
            
            // Update UI with compliance status
            this.showComplianceStatus(
                paragraphId, 
                data.overall_status, 
                data.overall_score,
                this.formatComplianceMessage(data),
                allConstraintViolations.length > 0 ? allConstraintViolations : null
            );
            
            // Update comment statuses
            this.updateCommentStatuses(data.compliance_results);
            
        } catch (error) {
            console.error('Real-time compliance check failed:', error);
            console.error('Error stack:', error.stack);
            this.showComplianceStatus(paragraphId, 'error', 0.0, `Failed: ${error.message}`);
        }
    }

    formatComplianceMessage(data) {
        if (data.total_comments === 0) {
            return 'No comments to check';
        }
        
        const score = Math.round(data.overall_score * 100);
        let message = `${data.total_comments} comment${data.total_comments > 1 ? 's' : ''} - ${score}% compliance`;
        
        // Check for constraint violations in any of the compliance results
        let totalConstraintViolations = 0;
        let constraintDetails = [];
        
        if (data.compliance_results) {
            for (const result of data.compliance_results) {
                if (result.constraint_validation && result.constraint_validation.violations) {
                    totalConstraintViolations += result.constraint_validation.violations.length;
                    constraintDetails.push(...result.constraint_validation.violations);
                }
            }
        }
        
        if (totalConstraintViolations > 0) {
            message += ` (${totalConstraintViolations} constraint violation${totalConstraintViolations > 1 ? 's' : ''})`;
        }
        
        if (data.can_auto_delete) {
            message += ' Can auto-delete';
        } else {
            message += ' Needs attention';
        }
        
        return message;
    }

    showComplianceStatus(paragraphId, status, score, message, constraintDetails = null) {
        const wrapper = document.querySelector(`.paragraph-wrapper[data-id="${paragraphId}"]`);
        if (!wrapper) {
            console.log('Could not find paragraph wrapper for ID:', paragraphId);
            return;
        }
        
        // Remove existing status
        let statusElement = wrapper.querySelector('.compliance-status');
        if (statusElement) {
            statusElement.remove();
        }
        
        // Create new status element
        statusElement = document.createElement('div');
        const statusClass = `compliance-status status-${status}`;
        statusElement.className = statusClass;
        
        console.log('Creating compliance status with class:', statusClass);
        console.log('Status details:', {status, score, message});
        
        // Add inline styles as fallback to ensure colors show
        let backgroundColor, borderColor, textColor;
        switch(status) {
            case 'compliant':
                backgroundColor = '#d4f6d4';
                borderColor = '#28a745';
                textColor = '#155724';
                break;
            case 'partial':
                backgroundColor = '#fff3cd';
                borderColor = '#ffc107';
                textColor = '#856404';
                break;
            case 'non_compliant':
                backgroundColor = '#f8d7da';
                borderColor = '#dc3545';
                textColor = '#721c24';
                break;
            case 'checking':
                backgroundColor = '#e2e8f0';
                borderColor = '#64748b';
                textColor = '#475569';
                break;
            default:
                backgroundColor = '#f1f5f9';
                borderColor = '#94a3b8';
                textColor = '#64748b';
        }
        
        statusElement.style.cssText = `
            display: flex !important;
            align-items: center;
            gap: 8px;
            padding: 6px 12px;
            margin: 8px 0;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            border: 1px solid ${borderColor};
            background-color: ${backgroundColor};
            color: ${textColor};
            transition: all 0.2s ease;
        `;
        
        let statusHTML = `
            <span class="status-icon">${this.getStatusIcon(status)}</span>
            <span class="status-text" style="flex: 1;">${message}</span>
            <span class="status-score" style="font-weight: bold; font-size: 12px; padding: 2px 6px; border-radius: 10px; background-color: rgba(0,0,0,0.1);">${Math.round(score * 100)}%</span>
        `;
        
        // Add constraint details if available
        if (constraintDetails && constraintDetails.length > 0) {
            statusHTML += `
                <div class="constraint-details" style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(0,0,0,0.1); width: 100%;">
                    <div style="font-size: 11px; font-weight: bold; margin-bottom: 4px;">Constraint Issues:</div>
            `;
            
            constraintDetails.forEach(detail => {
                statusHTML += `<div style="font-size: 11px; margin: 2px 0;">• ${detail}</div>`;
            });
            
            statusHTML += '</div>';
        }
        
        statusElement.innerHTML = statusHTML;
        
        // Insert before actions
        const actions = wrapper.querySelector('.paragraph-actions');
        if (actions) {
            wrapper.insertBefore(statusElement, actions);
        } else {
            wrapper.appendChild(statusElement);
        }
        
        console.log('Compliance status element created:', statusElement);
        console.log('Element computed styles:', window.getComputedStyle(statusElement));
    }

    clearComplianceStatus(paragraphId) {
        const wrapper = document.querySelector(`.paragraph-wrapper[data-id="${paragraphId}"]`);
        if (!wrapper) return;
        
        const statusElement = wrapper.querySelector('.compliance-status');
        if (statusElement) {
            statusElement.remove();
        }
    }

    getStatusIcon(status) {
        switch (status) {
            case 'compliant': return 'OK';
            case 'partial': return 'WARN';
            case 'non_compliant': return 'ERR';
            case 'checking': return 'CHK';
            case 'error': return 'ERR';
            default: return '?';
        }
    }

    updateCommentStatuses(complianceResults) {
        // Update comment display with compliance status
        complianceResults.forEach(result => {
            const commentElement = document.querySelector(`[data-comment-id="${result.comment_id}"]`);
            if (commentElement) {
                const statusSpan = commentElement.querySelector('.comment-status') || 
                    this.createCommentStatusElement(commentElement);
                
                statusSpan.className = `comment-status status-${result.status}`;
                statusSpan.innerHTML = `
                    ${this.getStatusIcon(result.status)} 
                    ${Math.round(result.score * 100)}%
                `;
                statusSpan.title = `Compliance: ${result.status} (${Math.round(result.confidence * 100)}% confidence)`;

                // Handle scheduled deletion information
                if (result.is_scheduled_for_deletion && result.scheduled_deletion_at) {
                    this.handleScheduledDeletion(commentElement, result.scheduled_deletion_at);
                } else if (result.status === 'compliant') {
                    // Clear any existing countdown if comment is no longer scheduled
                    this.clearScheduledDeletion(commentElement);
                }
            }
        });
    }

    createCommentStatusElement(commentElement) {
        const statusSpan = document.createElement('span');
        statusSpan.className = 'comment-status';
        
        // Insert after comment text
        const textElement = commentElement.querySelector('.comment-text');
        if (textElement) {
            textElement.appendChild(statusSpan);
        } else {
            commentElement.appendChild(statusSpan);
        }
        
        return statusSpan;
    }

    handleScheduledDeletion(commentElement, scheduledDeletionAt) {
        // Check if countdown already exists
        let countdownElement = commentElement.querySelector('.countdown-timer');
        
        if (!countdownElement) {
            // Create countdown timer element
            countdownElement = document.createElement('span');
            countdownElement.className = 'countdown-timer';
            commentElement.appendChild(countdownElement);
        }

        // Start countdown
        this.startCountdown(countdownElement, scheduledDeletionAt, commentElement);
    }

    clearScheduledDeletion(commentElement) {
        const countdownElement = commentElement.querySelector('.countdown-timer');
        const cancelButton = commentElement.querySelector('.cancel-deletion-btn');
        
        if (countdownElement) {
            // Clear any existing interval
            const intervalId = countdownElement.dataset.intervalId;
            if (intervalId) {
                clearInterval(parseInt(intervalId));
            }
            countdownElement.remove();
        }
        
        if (cancelButton) {
            cancelButton.remove();
        }
    }

    startCountdown(countdownElement, scheduledDeletionAt, commentElement) {
        const deletionTime = new Date(scheduledDeletionAt);
        
        // Clear any existing interval
        const existingIntervalId = countdownElement.dataset.intervalId;
        if (existingIntervalId) {
            clearInterval(parseInt(existingIntervalId));
        }
        
        const updateCountdown = () => {
            const now = new Date();
            const timeLeft = deletionTime - now;
            
            if (timeLeft <= 0) {
                countdownElement.textContent = '🗑️ Deleting...';
                const intervalId = countdownElement.dataset.intervalId;
                if (intervalId) {
                    clearInterval(parseInt(intervalId));
                }
                // Comment should be removed by the server shortly
                return;
            }
            
            const minutes = Math.floor(timeLeft / 60000);
            const seconds = Math.floor((timeLeft % 60000) / 1000);
            countdownElement.textContent = `🗑️ Deleting in ${minutes}:${seconds.toString().padStart(2, '0')}`;
            
            // Add cancel button if it doesn't exist
            if (!commentElement.querySelector('.cancel-deletion-btn')) {
                this.addCancelButton(commentElement);
            }
        };
        
        // Update immediately
        updateCountdown();
        
        // Set up interval for updates
        const intervalId = setInterval(updateCountdown, 1000);
        countdownElement.dataset.intervalId = intervalId.toString();
    }

    addCancelButton(commentElement) {
        const cancelButton = document.createElement('button');
        cancelButton.className = 'cancel-deletion-btn';
        cancelButton.textContent = '✖️ Cancel';
        cancelButton.title = 'Cancel scheduled deletion';
        
        const commentId = commentElement.dataset.commentId;
        cancelButton.onclick = () => this.cancelScheduledDeletion(commentId, commentElement);
        
        commentElement.appendChild(cancelButton);
    }

    createCommentElement(comment) {
        const element = super.createCommentElement(comment);
        
        // Add data attribute for comment ID
        element.dataset.commentId = comment.id;
        
        // Add compliance status placeholder
        const content = element.querySelector('.comment-content');
        if (content) {
            const statusWrapper = document.createElement('div');
            statusWrapper.className = 'comment-text';
            
            // Move existing text content to wrapper
            statusWrapper.textContent = content.textContent;
            content.textContent = '';
            content.appendChild(statusWrapper);
            
            // Create status element (will be populated by real-time checks)
            const statusElement = document.createElement('span');
            statusElement.className = 'comment-status';
            statusElement.style.marginLeft = '10px';
            statusWrapper.appendChild(statusElement);
        }
        
        return element;
    }

    scheduleAutoSave(paragraphId, text) {
        this.setSaveStatus('saving');
        
        if (this.saveTimeout) {
            clearTimeout(this.saveTimeout);
        }
        
        this.saveTimeout = setTimeout(async () => {
            try {
                await this.saveParagraph(paragraphId, text);
                this.setSaveStatus('saved');
                this.unsavedChanges = false;
                
                setTimeout(() => {
                    this.setSaveStatus('ready');
                }, 2000);
                
            } catch (error) {
                this.setSaveStatus('error');
                console.error('Auto-save error:', error);
            }
        }, 1000);
    }
    
    async saveParagraph(paragraphId, text) {
        try {
            const response = await fetch('/editor/api/edit_paragraph/', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    document_id: this.currentDocumentId,
                    paragraph_id: paragraphId,
                    text: text
                })
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('Save paragraph error response:', response.status, errorText);
                throw new Error(`Failed to save paragraph (${response.status}): ${errorText}`);
            }
            
            const responseData = await response.json();
            console.log('Save paragraph success:', responseData);
            
            // Handle automatic version creation - Updated for new behavior
            if (responseData.version_created && responseData.new_version_id) {
                console.log(`Auto-versioning occurred: ${responseData.version_message}`);
                
                // Show success message about version creation
                this.showStatus(responseData.version_message, 'success');
                
                // Load the new version after a short delay (stay on same page, no redirect)
                setTimeout(() => {
                    console.log('Loading new document version:', responseData.new_version_id);
                    this.loadDocument(responseData.new_version_id);
                }, 1500);
                
                return; // Don't continue with normal paragraph update
            }
            
            // Show progress message if available (when not all commented paragraphs are edited yet)
            if (responseData.version_message && !responseData.version_created) {
                this.showStatus(responseData.version_message, 'info');
            }
            
            // Show regular response message if available
            if (responseData.message) {
                this.showStatus(responseData.message, 'success');
            }
            
            const paraIndex = this.paragraphs.findIndex(p => p.id === paragraphId);
            if (paraIndex !== -1) {
                this.paragraphs[paraIndex].text = text;
                // Clear html_content so plain text will be used for display
                this.paragraphs[paraIndex].html_content = "";
                this.renderComments(); // Update comment list with new paragraph text
            }
        } catch (error) {
            console.error('Save paragraph failed:', error);
            throw error; // Re-throw to trigger auto-save error handling
        }
    }
    
    setSaveStatus(status) {
        const statusElement = document.getElementById('saveStatus');
        statusElement.className = 'save-status';
        
        switch (status) {
            case 'saving':
                statusElement.textContent = 'Saving...';
                statusElement.classList.add('saving');
                break;
            case 'saved':
                statusElement.textContent = 'Saved';
                statusElement.classList.add('saved');
                break;
            case 'error':
                statusElement.textContent = 'Error saving';
                statusElement.classList.add('error');
                break;
            default:
                statusElement.textContent = 'Ready';
        }
    }
    
    showDeleteModal(paragraphId) {
        const paragraph = this.paragraphs.find(p => p.id === paragraphId);
        if (!paragraph) return;
        
        if (this.paragraphs.length <= 1) {
            this.showStatus('Cannot delete the last paragraph', 'error');
            return;
        }
        
        this.pendingDeleteId = paragraphId;
        
        // Update modal content
        const preview = document.getElementById('paragraphPreview');
        const previewText = paragraph.text.substring(0, 100);
        preview.textContent = previewText + (paragraph.text.length > 100 ? '...' : '');
        
        // Show modal
        document.getElementById('deleteModal').style.display = 'block';
    }
    
    hideDeleteModal() {
        document.getElementById('deleteModal').style.display = 'none';
        this.pendingDeleteId = null;
    }
    
    async confirmDelete() {
        if (!this.pendingDeleteId) return;
        
        try {
            const response = await fetch('/editor/api/delete_paragraph/', {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    document_id: this.currentDocumentId,
                    paragraph_id: this.pendingDeleteId
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to delete paragraph');
            }
            
            // Update local data
            const deletedId = this.pendingDeleteId;
            
            this.paragraphs = this.paragraphs.filter(p => p.id !== deletedId);
            this.paragraphs.forEach(p => {
                if (p.id > deletedId) {
                    p.id -= 1;
                }
            });
            
            this.comments = this.comments.filter(c => c.paragraph_id !== deletedId);
            this.comments.forEach(c => {
                if (c.paragraph_id > deletedId) {
                    c.paragraph_id -= 1;
                }
            });
            
            this.renderDocument();
            this.renderComments();
            
            this.hideDeleteModal();
            
            let message = 'Paragraph deleted successfully';
            if (data.deleted_comments > 0) {
                message += ` (${data.deleted_comments} comment${data.deleted_comments > 1 ? 's' : ''} also deleted)`;
            }
            this.showStatus(message, 'success');
            
        } catch (error) {
            console.error('Error deleting paragraph:', error);
            this.showStatus(`Error deleting paragraph: ${error.message}`, 'error');
            this.hideDeleteModal();
        }
    }
    
    async duplicateParagraph(paragraphId) {
        const paragraph = this.paragraphs.find(p => p.id === paragraphId);
        if (!paragraph) return;
        
        try {
            const position = paragraphId + 1;
            
            const response = await fetch('/editor/api/add_paragraph/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    document_id: this.currentDocumentId,
                    text: paragraph.text,
                    position: position
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to duplicate paragraph');
            }
            
            // Update local data
            this.paragraphs.forEach(p => {
                if (p.id >= position) {
                    p.id += 1;
                }
            });
            
            this.paragraphs.push({
                id: position,
                text: paragraph.text
            });
            
            this.paragraphs.sort((a, b) => a.id - b.id);
            
            this.comments.forEach(c => {
                if (c.paragraph_id >= position) {
                    c.paragraph_id += 1;
                }
            });
            
            this.renderDocument();
            this.renderComments();
            
            this.showStatus('Paragraph duplicated successfully', 'success');
            
        } catch (error) {
            console.error('Error duplicating paragraph:', error);
            this.showStatus(`Error duplicating paragraph: ${error.message}`, 'error');
        }
    }

    async insertParagraphAfter(paragraphId) {
        try {
            const position = paragraphId + 1;
            
            // Get the current paragraph to copy its styling
            const currentParagraph = this.paragraphs.find(p => p.id === paragraphId);
            let inheritedHtmlContent = '';
            
            // If the current paragraph has HTML formatting, create a template for the new paragraph
            if (currentParagraph && currentParagraph.html_content && currentParagraph.html_content.trim()) {
                // Extract the HTML tag structure but with empty content
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = currentParagraph.html_content;
                
                // Get the first element (usually a p, h1, h2, etc.)
                const firstElement = tempDiv.firstElementChild;
                if (firstElement) {
                    // Clone the element but clear its content
                    const templateElement = firstElement.cloneNode(false);
                    templateElement.innerHTML = '';
                    inheritedHtmlContent = templateElement.outerHTML;
                }
            }
            
            const response = await fetch('/editor/api/add_paragraph/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    document_id: this.currentDocumentId,
                    text: '',
                    position: position
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to insert paragraph');
            }
            
            // Update local data
            this.paragraphs.forEach(p => {
                if (p.id >= position) {
                    p.id += 1;
                }
            });
            
            // Add new paragraph with inherited formatting
            const newParagraph = {
                id: position,
                text: '',
                html_content: inheritedHtmlContent
            };
            this.paragraphs.push(newParagraph);
            
            this.paragraphs.sort((a, b) => a.id - b.id);
            
            // Update comment references
            this.comments.forEach(c => {
                if (c.paragraph_id >= position) {
                    c.paragraph_id += 1;
                }
            });
            
            this.renderDocument();
            this.renderComments();
            
            // Focus the new paragraph
            requestAnimationFrame(() => {
                const newPara = document.querySelector(`.paragraph-wrapper[data-id="${position}"] .paragraph-content`);
                if (newPara) {
                    newPara.focus();
                }
            });
            
            this.showStatus('New paragraph inserted', 'success');
            
        } catch (error) {
            console.error('Error inserting paragraph:', error);
            this.showStatus(`Error inserting paragraph: ${error.message}`, 'error');
        }
    }
    
    // Progress tracking for commented paragraph editing
    updateProgressTracker() {
        if (!this.currentDocumentData || this.currentDocumentData.version_status !== 'commented') {
            this.hideProgressTracker();
            return;
        }
        
        const commentedParagraphs = this.getCommentedParagraphIds();
        if (commentedParagraphs.length === 0) {
            this.hideProgressTracker();
            return;
        }
        
        // Get edited commented paragraphs from document data or track locally
        const editedParagraphs = this.currentDocumentData.edited_commented_paragraphs || [];
        const progress = editedParagraphs.length;
        const total = commentedParagraphs.length;
        const percentage = total > 0 ? (progress / total) * 100 : 0;
        
        this.showProgressTracker(progress, total, percentage);
        this.updateParagraphIndicators(commentedParagraphs, editedParagraphs);
    }
    
    getCommentedParagraphIds() {
        if (!this.comments || !Array.isArray(this.comments)) return [];
        return [...new Set(this.comments.map(c => c.paragraph_id))];
    }
    
    showProgressTracker(progress, total, percentage) {
        let tracker = document.querySelector('.version-progress');
        if (!tracker) {
            tracker = document.createElement('div');
            tracker.className = 'version-progress';
            
            const toolbar = document.getElementById('toolbar');
            if (toolbar) {
                toolbar.parentNode.insertBefore(tracker, toolbar.nextSibling);
            }
        }
        
        const isComplete = progress >= total;
        tracker.className = `version-progress ${isComplete ? 'complete' : ''}`;
        
        tracker.innerHTML = `
            <div class="progress-text">
                ${isComplete 
                    ? `All commented paragraphs edited - new version will be created next!`
                    : `Editing progress: ${progress}/${total} commented paragraphs edited`
                }
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar" style="width: ${percentage}%"></div>
            </div>
        `;
    }
    
    hideProgressTracker() {
        const tracker = document.querySelector('.version-progress');
        if (tracker) {
            tracker.remove();
        }
    }
    
    updateParagraphIndicators(commentedParagraphs, editedParagraphs) {
        // Remove existing indicators
        document.querySelectorAll('.paragraph-wrapper').forEach(wrapper => {
            wrapper.classList.remove('has-unedited-comments', 'comment-edited');
        });
        
        // Add indicators for commented paragraphs
        commentedParagraphs.forEach(paragraphId => {
            const wrapper = document.querySelector(`.paragraph-wrapper[data-id="${paragraphId}"]`);
            if (wrapper) {
                if (editedParagraphs.includes(paragraphId)) {
                    wrapper.classList.add('comment-edited');
                } else {
                    wrapper.classList.add('has-unedited-comments');
                }
            }
        });
    }
    
    // Override the loadDocument method to include progress tracking
    async loadDocument(documentId) {
        await super.loadDocument(documentId);
        this.updateProgressTracker();
    }
    
    // Override renderDocument to update progress after rendering
    renderDocument() {
        super.renderDocument();
        this.updateProgressTracker();
        this.setupEmptyDocumentHandling();
    }

    setupEmptyDocumentHandling() {
        const content = document.getElementById('document-content');
        
        // If document is empty, add click handler to create first paragraph
        if (this.paragraphs.length === 0) {
            content.innerHTML = '<div class="empty-document-placeholder">Click here to start typing...</div>';
            
            const placeholder = content.querySelector('.empty-document-placeholder');
            placeholder.addEventListener('click', async () => {
                await this.insertParagraphAfter(0);
                // Focus on the new paragraph
                setTimeout(() => {
                    const firstParagraph = content.querySelector('.paragraph-content');
                    if (firstParagraph) {
                        firstParagraph.focus();
                    }
                }, 100);
            });
        } else {
            // For documents with content, add click handler for empty space at the end
            this.setupEndOfDocumentClicking();
        }
    }

    setupEndOfDocumentClicking() {
        const content = document.getElementById('document-content');
        
        content.addEventListener('click', async (e) => {
            // Check if click is in empty space after the last paragraph
            if (e.target === content || e.target.closest('.paragraph-wrapper') === null) {
                const rect = content.getBoundingClientRect();
                const clickY = e.clientY - rect.top;
                const lastParagraph = content.querySelector('.paragraph-wrapper:last-child');
                
                if (lastParagraph) {
                    const lastRect = lastParagraph.getBoundingClientRect();
                    const lastParagraphBottom = lastRect.bottom - rect.top;
                    
                    // If clicked below the last paragraph, add a new one
                    if (clickY > lastParagraphBottom + 10) { // 10px buffer
                        const lastParagraphId = parseInt(lastParagraph.dataset.id);
                        await this.insertParagraphAfter(lastParagraphId);
                        
                        // Focus on the new paragraph
                        setTimeout(() => {
                            const newParagraph = content.querySelector('.paragraph-wrapper:last-child .paragraph-content');
                            if (newParagraph) {
                                newParagraph.focus();
                            }
                        }, 100);
                    }
                }
            }
        });
    }

    isAtEndOfParagraph(element) {
        const selection = window.getSelection();
        if (selection.rangeCount === 0) return false;
        
        const range = selection.getRangeAt(0);
        return range.endOffset === element.textContent.length && range.collapsed;
    }

    getNextParagraph(currentId) {
        const currentIndex = this.paragraphs.findIndex(p => p.id === currentId);
        return currentIndex < this.paragraphs.length - 1 ? this.paragraphs[currentIndex + 1] : null;
    }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    window.docxApp = new DocxEditor();
});