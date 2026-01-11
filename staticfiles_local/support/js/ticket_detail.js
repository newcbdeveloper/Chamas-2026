// Support Ticket Detail JavaScript

class TicketChat {
    constructor(ticketId) {
        this.ticketId = ticketId;
        this.chatMessages = document.getElementById('chatMessages');
        this.lastMessageId = null;
        this.refreshInterval = 30000; // 30 seconds
        this.init();
    }

    init() {
        // Scroll to bottom on load
        this.scrollToBottom();
        
        // Mark messages as read
        this.markMessagesAsRead();
        
        // Auto-refresh messages
        setInterval(() => this.refreshMessages(), this.refreshInterval);
        
        // Setup event listeners
        this.setupEventListeners();
    }

    scrollToBottom() {
        if (this.chatMessages) {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }
    }

    scrollToBottomSmooth() {
        if (this.chatMessages) {
            this.chatMessages.scrollTo({
                top: this.chatMessages.scrollHeight,
                behavior: 'smooth'
            });
        }
    }

    async markMessagesAsRead() {
        try {
            const csrfToken = this.getCsrfToken();
            const response = await fetch(`/support/api/mark-read/${this.ticketId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                console.log('Messages marked as read');
            }
        } catch (error) {
            console.error('Error marking messages as read:', error);
        }
    }

    async refreshMessages() {
        try {
            const response = await fetch(`/support/api/messages/${this.ticketId}/`);
            const data = await response.json();

            if (data.success) {
                this.updateMessages(data.messages);
            }
        } catch (error) {
            console.error('Error refreshing messages:', error);
        }
    }

    updateMessages(messages) {
        // Get last message ID from DOM
        const lastMessage = this.chatMessages.querySelector('.chat-message:last-child');
        const currentLastId = lastMessage ? lastMessage.dataset.messageId : null;

        // Check if there are new messages
        const lastMessageId = messages.length > 0 ? messages[messages.length - 1].id : null;

        if (lastMessageId && lastMessageId !== currentLastId) {
            // New messages detected
            console.log('New messages detected, refreshing...');
            
            // For simplicity, reload the page (you can implement partial update)
            location.reload();
        }
    }

    async sendMessage(messageText, attachment = null) {
        try {
            const csrfToken = this.getCsrfToken();
            const formData = new FormData();
            formData.append('ticket_id', this.ticketId);
            formData.append('message', messageText);
            
            if (attachment) {
                formData.append('attachment', attachment);
            }

            const response = await fetch('/support/api/send-message/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                console.log('Message sent successfully');
                return true;
            } else {
                console.error('Error sending message:', data.error);
                return false;
            }
        } catch (error) {
            console.error('Error sending message:', error);
            return false;
        }
    }

    setupEventListeners() {
        // Handle Enter key to send
        const messageInput = document.querySelector('textarea[name="message"]');
        if (messageInput) {
            messageInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    const form = messageInput.closest('form');
                    if (form) {
                        form.submit();
                    }
                }
            });
        }
    }

    getCsrfToken() {
        const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (csrfInput) {
            return csrfInput.value;
        }
        
        // Fallback: get from cookie
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        document.body.appendChild(notification);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
}

// File upload handler
class FileUploadHandler {
    constructor(inputId, previewId) {
        this.input = document.getElementById(inputId);
        this.preview = document.getElementById(previewId);
        
        if (this.input) {
            this.init();
        }
    }

    init() {
        this.input.addEventListener('change', (e) => this.handleFileSelect(e));
    }

    handleFileSelect(e) {
        const file = e.target.files[0];
        
        if (!file) {
            this.clearPreview();
            return;
        }

        // Validate file size (5MB)
        const maxSize = 5 * 1024 * 1024;
        if (file.size > maxSize) {
            this.showError('File size exceeds 5MB limit');
            this.input.value = '';
            return;
        }

        // Validate file type
        const allowedTypes = [
            'image/jpeg',
            'image/png',
            'application/pdf',
            'text/plain',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ];

        if (!allowedTypes.includes(file.type)) {
            this.showError('File type not allowed');
            this.input.value = '';
            return;
        }

        // Show preview
        this.showPreview(file);
    }

    showPreview(file) {
        if (!this.preview) return;

        const fileSize = (file.size / 1024 / 1024).toFixed(2);
        const fileName = file.name;

        this.preview.innerHTML = `
            <div class="alert alert-info d-flex align-items-center justify-content-between">
                <div>
                    <i class="fas fa-file me-2"></i>
                    <strong>${fileName}</strong> (${fileSize} MB)
                </div>
                <button type="button" class="btn-close" onclick="this.closest('.alert').remove(); document.getElementById('${this.input.id}').value = '';"></button>
            </div>
        `;
    }

    clearPreview() {
        if (this.preview) {
            this.preview.innerHTML = '';
        }
    }

    showError(message) {
        if (this.preview) {
            this.preview.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>${message}
                </div>
            `;

            setTimeout(() => {
                this.clearPreview();
            }, 3000);
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Get ticket ID from URL or data attribute
    const ticketId = document.querySelector('[data-ticket-id]')?.dataset.ticketId;
    
    if (ticketId) {
        // Initialize ticket chat
        window.ticketChat = new TicketChat(ticketId);
    }

    // Initialize file upload handler
    window.fileUploadHandler = new FileUploadHandler('id_attachment', 'attachmentPreview');
});