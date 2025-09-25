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
        listContainer.className = 'documents-list';
        listContainer.innerHTML = '<h3>Available Documents</h3>';

        if (documents.length === 0) {
            listContainer.innerHTML += '<p>No documents available for editing</p>';
        } else {
            const list = document.createElement('ul');
            documents.forEach(doc => {
                const item = document.createElement('li');
                item.innerHTML = `<a href="#" data-id="${doc.id}">${doc.filename}</a>`;
                item.querySelector('a').addEventListener('click', (e) => {
                    e.preventDefault();
                    // Check for unsaved changes before switching documents
                    if (this.unsavedChanges && !confirm('You have unsaved changes. Are you sure you want to switch documents?')) {
                        return;
                    }
                    this.loadDocument(doc.id);
                });
                list.appendChild(item);
            });
            listContainer.appendChild(list);
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
                    
                    const response = await fetch(`/editor/api/document/${this.currentDocumentId}/export/`, {
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
            
            // Update UI with compliance status
            this.showComplianceStatus(
                paragraphId, 
                data.overall_status, 
                data.overall_score,
                this.formatComplianceMessage(data)
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
        
        if (data.can_auto_delete) {
            message += ' Can auto-delete';
        } else {
            message += ' Needs attention';
        }
        
        return message;
    }

    showComplianceStatus(paragraphId, status, score, message) {
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
        
        statusElement.innerHTML = `
            <span class="status-icon">${this.getStatusIcon(status)}</span>
            <span class="status-text" style="flex: 1;">${message}</span>
            <span class="status-score" style="font-weight: bold; font-size: 12px; padding: 2px 6px; border-radius: 10px; background-color: rgba(0,0,0,0.1);">${Math.round(score * 100)}%</span>
        `;
        
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
            
            // Add new paragraph
            const newParagraph = {
                id: position,
                text: ''
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
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    window.docxApp = new DocxEditor();
});