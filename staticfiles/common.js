class DocxBase {
    constructor() {
        this.currentDocumentId = null;
        this.paragraphs = [];
        this.comments = [];
        
        this.initUI();
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
    }
    
    async handleFileSelect(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        if (!file.name.endsWith('.docx')) {
            this.showStatus('Please select a .docx file', 'error');
            return;
        }
        
        const formData = new FormData();
        formData.append('document', file);
        
        try {
            this.showStatus('Uploading document...', 'info');
            
            const response = await fetch('/upload/', {
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
            const response = await fetch(`/document/${documentId}/`);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to load document');
            }
            
            this.currentDocumentId = data.document_id;
            this.paragraphs = data.paragraphs;
            this.comments = data.comments;
            
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
        content.textContent = para.text;
        
        wrapper.appendChild(content);
        
        return wrapper;
    }
    
    renderDocument() {
        const content = document.getElementById('document-content');
        content.innerHTML = '';
        
        this.paragraphs.sort((a, b) => a.id - b.id);
        
        for (const para of this.paragraphs) {
            content.appendChild(this.createParagraphWrapper(para));
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
        header.innerHTML = `
            <span class="comment-author">${comment.author}</span>
            <span class="comment-date">${new Date(comment.created_at).toLocaleDateString()}</span>
        `;
        
        const content = document.createElement('div');
        content.className = 'comment-content';
        content.textContent = comment.text;
        
        element.appendChild(header);
        element.appendChild(content);
        
        return element;
    }
}