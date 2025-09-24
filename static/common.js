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
            
            const response = await fetch(uploadPath, {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Upload failed');
            }
            
            this.showStatus('Document uploaded successfully!', 'success');
            await this.loadDocument(data.document_id);
            
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
            const isEditor = window.location.pathname.startsWith('/editor/');
            const documentPath = isEditor ? `/editor/api/document/${documentId}/` : `/commenter/api/document/${documentId}/`;
            const timestamp = new Date().getTime();
            
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
        
        if (this.comments.length === 0) {
            commentsList.innerHTML = '<div class="loading">No comments yet</div>';
            return;
        }
        
        const paragraphSelect = document.getElementById('paragraphSelect');
        if (paragraphSelect) {
            paragraphSelect.innerHTML = '<option value="">Select a paragraph...</option>';
            
            for (const para of this.paragraphs) {
                const option = document.createElement('option');
                option.value = para.id;
                option.textContent = `Paragraph ${para.id}: ${para.text.substring(0, 50)}...`;
                paragraphSelect.appendChild(option);
            }
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
        
        header.innerHTML = `
            <span class="comment-author">${comment.author}</span>
            <span class="comment-date" title="Created on ${formattedDate} at ${formattedTime}">
                ${formattedDate} ${formattedTime}
            </span>
        `;
        
        const content = document.createElement('div');
        content.className = 'comment-content';
        content.textContent = comment.text;
        
        element.appendChild(header);
        element.appendChild(content);
        
        return element;
    }
}