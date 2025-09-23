class DocxEditor extends DocxBase {
    constructor() {
        super();
        this.pendingDeleteId = null;
        this.initDeleteModal();
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

    createParagraphWrapper(para) {
        const wrapper = super.createParagraphWrapper(para);
        
        // Make paragraph content editable
        const content = wrapper.querySelector('.paragraph-content');
        content.contentEditable = true;
        
        content.addEventListener('input', (e) => {
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
        
        // Add paragraph actions
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
        
        wrapper.appendChild(actions);
        
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
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    new DocxEditor();
});