class DocxEditor extends DocxBase {
    constructor() {
        super();
        this.pendingDeleteId = null;
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
                        throw new Error('Failed to add comment');
                    }

                    const data = await response.json();
                    this.comments.push(data);
                    this.renderComments();

                    // Clear form
                    commentInput.value = '';
                    
                    // Highlight the paragraph
                    this.highlightParagraph(parseInt(paragraphSelect.value));
                    
                    this.showStatus('Comment added successfully', 'success');
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
            throw new Error('Failed to save paragraph');
        }
        
        const paraIndex = this.paragraphs.findIndex(p => p.id === paragraphId);
        if (paraIndex !== -1) {
            this.paragraphs[paraIndex].text = text;
            this.renderComments(); // Update comment list with new paragraph text
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