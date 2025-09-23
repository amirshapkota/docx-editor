/**
 * DocxCommenter class handles the commenting interface for DOCX documents.
 * Manages document listing, viewing, and commenting functionality.
 */
class DocxCommenter {
    /**
     * Initialize the DocxCommenter instance.
     * Sets up initial state and event listeners.
     */
    constructor() {
        // State management
        this.currentDocumentId = null;
        this.paragraphs = [];
        this.comments = [];
        this.selectedParagraphId = null;
        
        // Initialize components
        this.initEventListeners();
        this.initExportButton();
        this.loadDocumentsList();
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
    }

    async loadDocumentsList() {
        try {
            const response = await fetch('/commenter/api/documents/');
            if (!response.ok) {
                throw new Error('Failed to fetch documents');
            }
            const documents = await response.json();
            this.renderDocumentsList(documents);
        } catch (error) {
            this.showStatus(`Error loading documents: ${error.message}`, 'error');
        }
    }

    async loadDocument(documentId) {
        try {
            const response = await fetch(`/commenter/api/document/${documentId}/`);
            if (!response.ok) {
                throw new Error('Failed to load document');
            }
            
            const data = await response.json();
            this.currentDocumentId = documentId;
            this.paragraphs = data.paragraphs;
            this.comments = data.comments;
            
            this.renderDocument();
            this.renderComments();
            this.showCommentForm();
            this.showExportButton();
            
            this.showStatus('Document loaded successfully!', 'success');
            
        } catch (error) {
            this.showStatus(`Error loading document: ${error.message}`, 'error');
        }
    }

    renderDocumentsList(documents) {
        const listContainer = document.querySelector('.documents-list');
        const list = document.getElementById('documentsList');
        list.innerHTML = ''; // Clear existing list

        if (!documents || documents.length === 0) {
            list.innerHTML = '<li class="no-documents">No documents available for commenting</li>';
        } else {
            documents.forEach(doc => {
                const item = document.createElement('li');
                const formattedDate = new Date(doc.uploaded_at).toLocaleDateString();
                item.innerHTML = `
                    <a href="#" data-id="${doc.id}">
                        <span class="doc-name">${doc.filename}</span>
                        <span class="doc-date">${formattedDate}</span>
                    </a>`;
                item.querySelector('a').addEventListener('click', (e) => {
                    e.preventDefault();
                    this.loadDocument(doc.id);
                });
                list.appendChild(item);
            });
        }

        listContainer.style.display = 'block';

        const style = document.createElement('style');
        style.textContent = `
            .documents-list {
                margin-bottom: 20px;
                padding: 15px;
                background: #f8f9fa;
                border-radius: 8px;
                border: 1px solid #dee2e6;
            }
            .documents-list ul {
                list-style: none;
                padding: 0;
                margin: 0;
            }
            .documents-list li {
                margin: 8px 0;
            }
            .documents-list a {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px;
                background: white;
                border-radius: 4px;
                color: #333;
                text-decoration: none;
                transition: all 0.2s ease;
            }
            .documents-list a:hover {
                background: #e9ecef;
                transform: translateX(5px);
            }
            .doc-name {
                font-weight: 500;
            }
            .doc-date {
                color: #6c757d;
                font-size: 0.9em;
            }
            .no-documents {
                color: #6c757d;
                text-align: center;
                padding: 20px;
                font-style: italic;
            }
            .paragraph-wrapper {
                position: relative;
                padding: 10px;
                margin: 5px 0;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                cursor: pointer;
            }
            .paragraph-wrapper.selected {
                background-color: #e9ecef;
                border-color: #007bff;
            }
            .paragraph-content {
                margin: 0;
                line-height: 1.5;
            }
            .comment {
                border: 1px solid #dee2e6;
                padding: 10px;
                margin: 5px 0;
                border-radius: 4px;
                cursor: pointer;
            }
            .comment-author {
                font-weight: bold;
                color: #007bff;
                margin-bottom: 5px;
            }
            .comment-text {
                margin-bottom: 5px;
            }
            .comment-para {
                font-size: 0.8em;
                color: #6c757d;
            }
            .loading {
                text-align: center;
                color: #6c757d;
                padding: 20px;
                font-style: italic;
            }
            .hidden {
                display: none;
            }
            .status {
                padding: 10px;
                margin: 10px 0;
                border-radius: 4px;
                opacity: 1;
                transition: opacity 0.3s ease;
            }
            .status.success {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            .status.error {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            .status.hidden {
                opacity: 0;
            }
        `;
        document.head.appendChild(style);
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
        formData.append('is_editable', 'false');  // This is for commenting only
        
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
            this.showCommentForm();
            this.showExportButton();
            
            this.showStatus('Document loaded successfully!', 'success');
            this.loadDocumentsList();  // Refresh the documents list after upload
            
        } catch (error) {
            console.error('Upload error:', error);
            this.showStatus('Error uploading document', 'error');
        }
    }
    
    renderDocument() {
        const container = document.getElementById('document-content');
        container.innerHTML = '';
        
        this.paragraphs.forEach((para) => {
            const wrapper = document.createElement('div');
            wrapper.className = 'paragraph-wrapper';
            wrapper.dataset.paragraphId = para.id;
            
            const content = document.createElement('div');
            content.className = 'paragraph-content';
            content.textContent = para.text;
            
            wrapper.appendChild(content);
            wrapper.addEventListener('click', () => this.selectParagraph(para.id));
            
            container.appendChild(wrapper);
        });
        
        this.updateCommentDropdown();
    }
    
    selectParagraph(paragraphId) {
        document.querySelectorAll('.paragraph-wrapper').forEach(wrapper => {
            wrapper.classList.remove('selected');
        });
        
        const wrapper = document.querySelector(`[data-paragraph-id="${paragraphId}"]`);
        if (wrapper) {
            wrapper.classList.add('selected');
        }
        
        this.selectedParagraphId = paragraphId;
        document.getElementById('paragraphSelect').value = paragraphId;
    }
    
    updateCommentDropdown() {
        const select = document.getElementById('paragraphSelect');
        select.innerHTML = '<option value="">Select a paragraph...</option>';
        
        this.paragraphs.forEach(para => {
            const option = document.createElement('option');
            option.value = para.id;
            option.textContent = `Paragraph ${para.id}: ${para.text.substring(0, 50)}${para.text.length > 50 ? '...' : ''}`;
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
                <div class="comment-para">Paragraph ${comment.paragraph_id}</div>
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
            
            document.getElementById('commentInput').value = '';
            this.renderComments();
            this.showStatus('Comment added successfully!', 'success');
            
        } catch (error) {
            this.showStatus(`Error adding comment: ${error.message}`, 'error');
        }
    }
    
    showCommentForm() {
        document.getElementById('addCommentForm').style.display = 'block';
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

    initExportButton() {
        const exportBtn = document.getElementById('exportBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', async () => {
                try {
                    if (!this.currentDocumentId) {
                        this.showStatus('Please select a document first', 'error');
                        return;
                    }

                    this.showStatus('Exporting document...', 'info');

                    const response = await fetch(`/commenter/api/document/${this.currentDocumentId}/export/`, {
                        method: 'GET'
                    });

                    if (!response.ok) {
                        throw new Error('Export failed');
                    }

                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'exported_document.docx';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);

                    this.showStatus('Document exported successfully', 'success');
                } catch (error) {
                    console.error('Export error:', error);
                    this.showStatus('Error exporting document: ' + error.message, 'error');
                }
            });
        }
    }

    showExportButton() {
        document.getElementById('export-section').style.display = 'block';
    }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    new DocxCommenter();
});