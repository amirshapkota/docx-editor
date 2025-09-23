class DocxCommenter {
    constructor() {
        this.currentDocumentId = null;
        this.paragraphs = [];
        this.comments = [];
        this.selectedParagraphId = null;
        this.saveTimeout = null;
        
        this.initEventListeners();
        window.docCommenter = this;
    }
    
    initEventListeners() {
        // File upload
        const fileInput = document.getElementById('fileInput');
        const uploadBtn = document.getElementById('uploadBtn');
        const uploadArea = document.getElementById('uploadArea');
        
        fileInput.addEventListener('change', () => this.handleFileSelect());
        uploadBtn.addEventListener('click', () => fileInput.click());
        
        // Drag and drop
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
                this.handleFileSelect();
            }
        });
        
        // Comments
        document.getElementById('saveCommentBtn').addEventListener('click', () => this.addComment());
        
        // Export
        document.getElementById('exportBtn').addEventListener('click', () => this.exportDocument());
    }
    
    async handleFileSelect() {
        const fileInput = document.getElementById('fileInput');
        const file = fileInput.files[0];
        
        if (!file) return;
        
        if (!file.name.endsWith('.docx')) {
            this.showStatus('Please select a .docx file', 'error');
            return;
        }
        
        this.showStatus('Uploading document...', 'success');
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/commenter/api/upload/', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error('Upload failed');
            }
            
            const data = await response.json();
            this.currentDocumentId = data.document_id;
            this.paragraphs = data.paragraphs;
            this.comments = data.comments;
            
            this.renderDocument();
            this.renderComments();
            this.showToolbar();
            this.showCommentForm();
            this.showExportButton();
            
            this.showStatus('Document loaded successfully!', 'success');
            
        } catch (error) {
            console.error('Upload error:', error);
            this.showStatus('Error uploading document', 'error');
        }
    }
    
    renderDocument() {
        const container = document.getElementById('document-content');
        container.innerHTML = '';
        
        const editorContainer = document.createElement('div');
        editorContainer.className = 'editor-container';
        
        this.paragraphs.forEach((para) => {
            const paraWrapper = this.createParagraphWrapper(para);
            editorContainer.appendChild(paraWrapper);
        });
        
        container.appendChild(editorContainer);
        this.updateCommentDropdown();
    }
    
    createParagraphWrapper(para) {
        const wrapper = document.createElement('div');
        wrapper.className = 'paragraph-wrapper';
        wrapper.dataset.paragraphId = para.id;
        
        // Paragraph marker
        const marker = document.createElement('div');
        marker.className = 'paragraph-marker';
        marker.textContent = para.id;
        marker.addEventListener('click', () => this.selectParagraph(para.id));
        wrapper.appendChild(marker);
        
        // Paragraph content (read-only)
        const content = document.createElement('div');
        content.className = 'paragraph-content';
        content.textContent = para.text;
        content.dataset.paragraphId = para.id;
        content.addEventListener('click', () => this.selectParagraph(para.id));
        
        wrapper.appendChild(content);
        
        return wrapper;
    }
    
    selectParagraph(paragraphId) {
        // Remove previous selections
        document.querySelectorAll('.paragraph-wrapper').forEach(wrapper => {
            wrapper.classList.remove('selected');
        });
        
        // Select current paragraph
        const wrapper = document.querySelector(`[data-paragraph-id="${paragraphId}"]`);
        if (wrapper) {
            wrapper.classList.add('selected');
        }
        
        this.selectedParagraphId = paragraphId;
        document.getElementById('paragraphSelect').value = paragraphId;
    }
    
    updateCommentDropdown() {
        const select = document.getElementById('paragraphSelect');
        select.innerHTML = '<option value="">Click on a paragraph...</option>';
        
        this.paragraphs.forEach(para => {
            const option = document.createElement('option');
            option.value = para.id;
            option.textContent = `${para.id}. ${para.text.substring(0, 50)}${para.text.length > 50 ? '...' : ''}`;
            select.appendChild(option);
        });
    }
    
    renderComments() {
        const container = document.getElementById('commentsList');
        
        if (this.comments.length === 0) {
            container.innerHTML = '<div class="loading">No comments yet</div>';
            return;
        }
        
        container.innerHTML = '';
        
        this.comments.forEach(comment => {
            const commentElement = document.createElement('div');
            commentElement.className = 'comment';
            commentElement.innerHTML = `
                <div class="comment-author">${comment.author}</div>
                <div class="comment-text">${comment.text}</div>
            `;
            
            commentElement.addEventListener('click', () => {
                this.selectParagraph(comment.paragraph_id);
            });
            
            container.appendChild(commentElement);
        });
    }
    
    async addComment() {
        const paragraphId = this.selectedParagraphId || document.getElementById('paragraphSelect').value;
        const author = document.getElementById('authorInput').value.trim() || 'Anonymous';
        const text = document.getElementById('commentInput').value.trim();
        
        if (!paragraphId || !text) {
            this.showStatus('Please select a paragraph and enter comment text', 'error');
            return;
        }
        
        try {
            const response = await fetch('/commenter/api/add_comment/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    document_id: this.currentDocumentId,
                    paragraph_id: parseInt(paragraphId),
                    author: author,
                    text: text
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to add comment');
            }
            
            const newComment = await response.json();
            this.comments.push(newComment);
            
            // Clear form
            document.getElementById('commentInput').value = '';
            
            this.renderComments();
            this.showStatus('Comment added successfully!', 'success');
            
        } catch (error) {
            console.error('Error adding comment:', error);
            this.showStatus('Error adding comment', 'error');
        }
    }
    
    async exportDocument() {
        if (!this.currentDocumentId) return;
        
        try {
            const response = await fetch(`/commenter/api/document/${this.currentDocumentId}/export/`);
            
            if (!response.ok) {
                throw new Error('Export failed');
            }
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `commented_document.docx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            this.showStatus('Document exported successfully!', 'success');
            
        } catch (error) {
            console.error('Export error:', error);
            this.showStatus('Error exporting document', 'error');
        }
    }
    
    showToolbar() {
        document.getElementById('toolbar').style.display = 'flex';
    }
    
    showCommentForm() {
        document.getElementById('addCommentForm').style.display = 'block';
    }
    
    showExportButton() {
        document.getElementById('export-section').style.display = 'block';
    }
    
    showStatus(message, type) {
        const statusElement = document.getElementById('status');
        statusElement.textContent = message;
        statusElement.className = `status ${type}`;
        statusElement.classList.remove('hidden');
        
        setTimeout(() => {
            statusElement.classList.add('hidden');
        }, 5000);
    }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    new DocxCommenter();
});