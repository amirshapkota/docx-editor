class DocxBase {
    constructor() {
        this.currentDocumentId = null;
        this.paragraphs = [];
        this.comments = [];
        this.unsavedChanges = false;
        this.selectedParagraphId = null;
        
        this.initUI();
        this.initWindowEvents();
    }
    
    initUI() {
        const uploadBtn = document.getElementById('uploadBtn');
        const fileInput = document.getElementById('fileInput');
        const uploadArea = document.getElementById('uploadArea');
        
        if (uploadBtn && fileInput) {
            uploadBtn.addEventListener('click', () => fileInput.click());
            fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
            
            // Drag and drop handling
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            
            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });
            
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    fileInput.files = files;
                    this.handleFileSelect({ target: fileInput });
                }
            });
        }
        
        // Initialize paragraph select event
        const paragraphSelect = document.getElementById('paragraphSelect');
        if (paragraphSelect) {
            paragraphSelect.addEventListener('change', (e) => {
                const paragraphId = e.target.value;
                if (paragraphId) {
                    this.highlightParagraph(parseInt(paragraphId));
                }
            });
        }
    }
    
    initWindowEvents() {
        window.addEventListener('beforeunload', (e) => {
            if (this.unsavedChanges) {
                e.preventDefault();
                e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
            }
        });
    }
    
    highlightParagraph(paragraphId) {
        // Remove existing highlights
        document.querySelectorAll('.paragraph-wrapper').forEach(p => {
            p.classList.remove('highlighted');
        });
        
        // Add highlight to selected paragraph
        const paragraph = document.querySelector(`.paragraph-wrapper[data-id="${paragraphId}"]`);
        if (paragraph) {
            paragraph.classList.add('highlighted');
            paragraph.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
    
    async handleFileSelect(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        if (!file.name.endsWith('.docx')) {
            this.showStatus('Please select a .docx file', 'error');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            this.showStatus('Uploading document...', 'info');
            
            const isEditor = window.location.pathname.startsWith('/editor/');
            const uploadPath = isEditor ? '/editor/api/upload/' : '/commenter/api/upload/';
            
            console.log('Starting upload to:', uploadPath);
            
            const response = await fetch(uploadPath, {
                method: 'POST',
                body: formData
            });
            
            console.log('Upload response status:', response.status, response.statusText);
            
            const data = await response.json();
            console.log('Upload response data:', data);
            
            if (!response.ok) {
                console.error('Upload failed with response:', data);
                throw new Error(data.error || 'Upload failed');
            }
            
            this.showStatus('Document uploaded successfully!', 'success');
            // Debug: Log the response to see its structure
            console.log('Upload response data:', data);
            console.log('data.data:', data.data);
            console.log('data.document_id:', data.document_id);
            
            // Extract document_id from the nested response structure
            let documentId = null;
            if (data.data && data.data.document_id) {
                documentId = data.data.document_id;
                console.log('Using nested document ID:', documentId);
            } else if (data.document_id) {
                documentId = data.document_id;
                console.log('Using flat document ID:', documentId);
            } else {
                console.error('No document_id found in response:', data);
                throw new Error('No document ID returned from upload');
            }
            
            console.log('Final extracted document ID:', documentId);
            await this.loadDocument(documentId);
            
        } catch (error) {
            console.error('Upload error:', error);
            this.showStatus('Error uploading document: ' + error.message, 'error');
        }
    }
    
    showStatus(message, type = 'info') {
        const status = document.getElementById('status');
        status.textContent = message;
        status.className = 'status ' + type;
        status.classList.remove('hidden');
        
        setTimeout(() => {
            status.classList.add('hidden');
        }, 5000);
    }
    
    async loadDocument(documentId) {
        try {
            console.log('loadDocument called with ID:', documentId);
            const isEditor = window.location.pathname.startsWith('/editor/');
            const documentPath = isEditor ? `/editor/api/document/${documentId}/` : `/commenter/api/document/${documentId}/`;
            const timestamp = new Date().getTime();
            
            console.log('Fetching document from:', documentPath + '?t=' + timestamp);
            const response = await fetch(documentPath + '?t=' + timestamp);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to load document');
            }
            
            this.currentDocumentId = data.document_id;
            this.paragraphs = data.paragraphs;
            this.comments = data.comments;
            this.unsavedChanges = false;
            
            this.renderDocument();
            this.renderComments();
            
            // Show toolbar and comment form
            document.getElementById('toolbar').style.display = 'block';
            document.getElementById('addCommentForm').style.display = 'block';
            document.getElementById('export-section').style.display = 'block';
            
        } catch (error) {
            console.error('Error loading document:', error);
            this.showStatus('Error loading document: ' + error.message, 'error');
        }
    }
    
    createParagraphWrapper(para) {
        const wrapper = document.createElement('div');
        wrapper.className = 'paragraph-wrapper';
        wrapper.dataset.id = para.id;
        
        const content = document.createElement('div');
        content.className = 'paragraph-content';
        
        // Use HTML content if available, otherwise fall back to plain text
        if (para.html_content && para.html_content.trim()) {
            content.innerHTML = para.html_content;
            
            // Make images clickable for viewing
            const images = content.querySelectorAll('.document-image');
            images.forEach(img => {
                img.addEventListener('click', () => this.showImageModal(img));
                img.style.cursor = 'pointer';
                img.style.maxWidth = '100%';
                img.style.height = 'auto';
            });
        } else if (para.text && para.text.trim()) {
            content.textContent = para.text;
        } else {
            content.innerHTML = '<em style="color: #666;">Empty paragraph</em>';
        }
        
        // Add click handler for paragraph selection
        content.addEventListener('click', () => {
            this.selectParagraph(para.id);
        });
        
        wrapper.appendChild(content);
        
        return wrapper;
    }
    
    showImageModal(img) {
        // Create a modal to show the full-size image
        const modal = document.createElement('div');
        modal.className = 'image-modal';
        modal.innerHTML = `
            <div class="image-modal-content">
                <span class="close-modal">&times;</span>
                <img src="${img.src}" alt="${img.alt}" style="max-width: 90%; max-height: 90%;">
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Close modal handlers
        const closeBtn = modal.querySelector('.close-modal');
        closeBtn.addEventListener('click', () => document.body.removeChild(modal));
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
            }
        });
    }
    
    selectParagraph(paragraphId) {
        // Remove previous selection
        document.querySelectorAll('.paragraph-wrapper').forEach(el => {
            el.classList.remove('selected');
        });
        
        // Select current paragraph
        const wrapper = document.querySelector(`[data-id="${paragraphId}"]`);
        if (wrapper) {
            wrapper.classList.add('selected');
        }
        
        // Update paragraph select dropdown
        const select = document.getElementById('paragraphSelect');
        if (select) {
            select.value = paragraphId;
        }
        
        this.selectedParagraphId = paragraphId;
    }
    
    renderDocument() {
        const content = document.getElementById('document-content');
        content.innerHTML = '';
        
        // Safety check: ensure paragraphs is defined and is an array
        if (!this.paragraphs || !Array.isArray(this.paragraphs)) {
            console.error('renderDocument called with invalid paragraphs:', this.paragraphs);
            content.innerHTML = '<div class="loading">Error: No paragraphs data available</div>';
            return;
        }
        
        this.paragraphs.sort((a, b) => a.id - b.id);
        
        for (const para of this.paragraphs) {
            // Add paragraph
            const wrapper = this.createParagraphWrapper(para);
            content.appendChild(wrapper);
            
            // Add "Add paragraph" button after each paragraph
            const addButton = document.createElement('button');
            addButton.className = 'add-paragraph-button';
            addButton.addEventListener('click', () => {
                this.insertParagraphAfter(para.id);
            });
            content.appendChild(addButton);
        }
        
        // Add final "Add paragraph" button if there are no paragraphs
        if (this.paragraphs.length === 0) {
            const addButton = document.createElement('button');
            addButton.className = 'add-paragraph-button';
            addButton.addEventListener('click', () => {
                this.insertParagraphAfter(0);
            });
            content.appendChild(addButton);
        }
    }
    
    renderComments() {
        const commentsList = document.getElementById('commentsList');
        commentsList.innerHTML = '';
        
        // Always populate the paragraph dropdown, regardless of whether comments exist
        const paragraphSelect = document.getElementById('paragraphSelect');
        if (paragraphSelect && this.paragraphs) {
            paragraphSelect.innerHTML = '<option value="">Select a paragraph...</option>';
            
            for (const para of this.paragraphs) {
                const option = document.createElement('option');
                option.value = para.id;
                option.textContent = `Paragraph ${para.id}: ${para.text.substring(0, 50)}...`;
                paragraphSelect.appendChild(option);
            }
        }
        
        if (this.comments.length === 0) {
            commentsList.innerHTML = '<div class="loading">No comments yet</div>';
            return;
        }
        
        // Group comments by paragraph
        const commentsByParagraph = {};
        for (const comment of this.comments) {
            if (!commentsByParagraph[comment.paragraph_id]) {
                commentsByParagraph[comment.paragraph_id] = [];
            }
            commentsByParagraph[comment.paragraph_id].push(comment);
        }
        
        // Sort comments by paragraph_id and then by created_at
        const sortedParagraphIds = Object.keys(commentsByParagraph).sort((a, b) => Number(a) - Number(b));
        
        for (const paragraphId of sortedParagraphIds) {
            const comments = commentsByParagraph[paragraphId];
            comments.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
            
            const paragraphComments = document.createElement('div');
            paragraphComments.className = 'paragraph-comments';
            
            const paragraph = this.paragraphs.find(p => p.id === Number(paragraphId));
            if (paragraph) {
                const header = document.createElement('h4');
                header.textContent = `Paragraph ${paragraphId}:`;
                header.title = paragraph.text;
                
                // Add click handler to highlight paragraph
                header.style.cursor = 'pointer';
                header.addEventListener('click', () => this.highlightParagraph(Number(paragraphId)));
                
                paragraphComments.appendChild(header);
            }
            
            for (const comment of comments) {
                const commentElement = this.createCommentElement(comment);
                paragraphComments.appendChild(commentElement);
            }
            
            commentsList.appendChild(paragraphComments);
        }
    }
    
    createCommentElement(comment) {
        const element = document.createElement('div');
        element.className = 'comment';
        
        const header = document.createElement('div');
        header.className = 'comment-header';
        
        const date = new Date(comment.created_at);
        const formattedDate = date.toLocaleDateString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
        const formattedTime = date.toLocaleTimeString(undefined, {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        // Create header with author and date
        const authorSpan = document.createElement('span');
        authorSpan.className = 'comment-author';
        authorSpan.textContent = comment.author;
        
        const dateSpan = document.createElement('span');
        dateSpan.className = 'comment-date';
        dateSpan.title = `Created on ${formattedDate} at ${formattedTime}`;
        dateSpan.textContent = `${formattedDate} ${formattedTime}`;
        
        // Check if comment is scheduled for deletion
        if (comment.scheduled_deletion_at) {
            const scheduledDate = new Date(comment.scheduled_deletion_at);
            const countdownContainer = document.createElement('div');
            countdownContainer.className = 'comment-countdown';
            
            const countdownText = document.createElement('span');
            countdownText.className = 'countdown-text';
            countdownContainer.appendChild(countdownText);
            
            const cancelBtn = document.createElement('button');
            cancelBtn.className = 'comment-cancel-btn';
            cancelBtn.textContent = 'Cancel Deletion';
            cancelBtn.title = 'Cancel scheduled deletion';
            cancelBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.cancelScheduledDeletion(comment.comment_id);
            });
            countdownContainer.appendChild(cancelBtn);
            
            // Start countdown timer
            const updateCountdown = () => {
                const now = new Date();
                const timeLeft = scheduledDate - now;
                
                if (timeLeft <= 0) {
                    countdownText.textContent = '⚠️ Comment expired - will be deleted soon';
                    countdownText.className = 'countdown-text expired';
                    cancelBtn.disabled = true;
                    return;
                }
                
                const minutes = Math.floor(timeLeft / (1000 * 60));
                const seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);
                countdownText.textContent = `🗑️ Deleting in ${minutes}:${seconds.toString().padStart(2, '0')}`;
                countdownText.className = 'countdown-text warning';
            };
            
            updateCountdown();
            const countdownInterval = setInterval(updateCountdown, 1000);
            
            // Store interval ID for cleanup
            countdownContainer.setAttribute('data-interval-id', countdownInterval);
            
            header.appendChild(countdownContainer);
        }
        
        // Create delete button (only if not scheduled for deletion)
        let deleteBtn = null;
        if (!comment.scheduled_deletion_at) {
            deleteBtn = document.createElement('button');
            deleteBtn.className = 'comment-delete-btn';
            deleteBtn.innerHTML = '×';
            deleteBtn.title = 'Delete comment';
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteComment(comment.comment_id);
            });
        }
        
        // Assemble header
        header.appendChild(authorSpan);
        header.appendChild(dateSpan);
        if (deleteBtn) {
            header.appendChild(deleteBtn);
        }
        
        const content = document.createElement('div');
        content.className = 'comment-content';
        content.textContent = comment.text;
        
        element.appendChild(header);
        element.appendChild(content);
        
        return element;
    }

    async deleteComment(commentId) {
        if (!confirm('Are you sure you want to delete this comment?')) {
            return;
        }

        try {
            const isEditor = window.location.pathname.startsWith('/editor/');
            const apiPath = isEditor ? '/editor/api/delete_comment/' : '/commenter/api/delete_comment/';
            
            const response = await fetch(apiPath, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    document_id: this.currentDocumentId,
                    comment_id: commentId
                })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to delete comment');
            }
            
            // Remove comment from local data
            this.comments = this.comments.filter(c => c.comment_id !== commentId);
            
            // Re-render comments
            this.renderComments();
            
            this.showStatus('Comment deleted successfully', 'success');
            
        } catch (error) {
            console.error('Error deleting comment:', error);
            this.showStatus('Error deleting comment: ' + error.message, 'error');
        }
    }
    
    async cancelScheduledDeletion(commentId) {
        try {
            const response = await fetch('/editor/api/ml/cancel-scheduled-deletion/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    document_id: this.currentDocumentId,
                    comment_id: commentId
                })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to cancel scheduled deletion');
            }
            
            const result = await response.json();
            
            // Update local comment data to remove scheduled deletion
            const comment = this.comments.find(c => c.id === commentId);
            if (comment) {
                comment.scheduled_deletion_at = null;
                comment.is_scheduled_for_deletion = false;
            }
            
            // Re-render comments to update UI
            this.renderComments();
            
            this.showStatus('Scheduled deletion cancelled successfully', 'success');
            
        } catch (error) {
            console.error('Error cancelling scheduled deletion:', error);
            this.showStatus('Error cancelling scheduled deletion: ' + error.message, 'error');
        }
    }
}