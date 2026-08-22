// Modern AI Chatbot Interaction Handler

document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chatForm');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatMessages = document.getElementById('chatMessages');
    const clearChatBtn = document.getElementById('clearChatBtn');
    const suggestionChips = document.querySelectorAll('.suggestion-chip');

    let chatHistory = [];

    // Auto focus input
    if (userInput) userInput.focus();

    // Suggestion chips click
    suggestionChips.forEach(chip => {
        chip.addEventListener('click', function() {
            const question = this.getAttribute('data-question');
            if (question) {
                sendMessage(question);
            }
        });
    });

    // Clear chat
    if (clearChatBtn) {
        clearChatBtn.addEventListener('click', function() {
            chatHistory = [];
            chatMessages.innerHTML = `
                <div class="chat-message bot-message animate-fade-up">
                    <div class="message-avatar"><i class="fas fa-robot"></i></div>
                    <div class="message-content">
                        <p>Chat cleared! Feel free to ask any financial or budgeting questions.</p>
                    </div>
                </div>
            `;
        });
    }

    // Submit message
    if (chatForm) {
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const text = userInput.value.trim();
            if (text) {
                sendMessage(text);
                userInput.value = '';
            }
        });
    }

    // Send message function
    async function sendMessage(text) {
        // Append user message
        appendMessage('user', text);
        chatHistory.push({ sender: 'user', text: text });

        // Show typing indicator
        const typingId = showTypingIndicator();
        sendBtn.disabled = true;

        try {
            const response = await fetch('/api/chatbot/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: text,
                    history: chatHistory
                })
            });

            removeTypingIndicator(typingId);
            sendBtn.disabled = false;

            if (response.ok) {
                const data = await response.json();
                const botReply = data.reply || "I analyzed your query but have no response.";
                appendMessage('bot', botReply);
                chatHistory.push({ sender: 'bot', text: botReply });
            } else {
                appendMessage('bot', "⚠️ Sorry, there was an issue processing your request. Please try again.");
            }
        } catch (error) {
            console.error('Chat error:', error);
            removeTypingIndicator(typingId);
            sendBtn.disabled = false;
            appendMessage('bot', "⚠️ Network connection error. Please verify your internet and try again.");
        }
    }

    // Append Message to UI
    function appendMessage(sender, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${sender}-message animate-fade-up`;

        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        avatarDiv.innerHTML = sender === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = formatMarkdown(text);

        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);

        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Typing indicator
    function showTypingIndicator() {
        const typingDiv = document.createElement('div');
        const id = 'typing-' + Date.now();
        typingDiv.id = id;
        typingDiv.className = 'chat-message bot-message typing-indicator-msg';
        typingDiv.innerHTML = `
            <div class="message-avatar"><i class="fas fa-robot"></i></div>
            <div class="message-content typing-bubble">
                <span class="dot"></span>
                <span class="dot"></span>
                <span class="dot"></span>
            </div>
        `;
        chatMessages.appendChild(typingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return id;
    }

    function removeTypingIndicator(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    // Markdown Formatter Helper
    function formatMarkdown(text) {
        if (!text) return '';
        let formatted = text
            // Escape html special chars
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            // Headers
            .replace(/^### (.*$)/gim, '<h4 class="chat-heading">$1</h4>')
            .replace(/^## (.*$)/gim, '<h3 class="chat-heading">$1</h3>')
            // Bold
            .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
            // Italic
            .replace(/\*(.*?)\*/gim, '<em>$1</em>')
            // Inline code
            .replace(/`(.*?)`/gim, '<code class="chat-code">$1</code>')
            // Unordered list items
            .replace(/^\- (.*$)/gim, '<li>$1</li>')
            // Numbered list items
            .replace(/^\d+\.\s+(.*$)/gim, '<li>$1</li>')
            // Newlines
            .replace(/\n/g, '<br>');

        // Wrap consecutive li in ul
        formatted = formatted.replace(/(<li>.*<\/li>)/gis, '<ul class="chat-list">$1</ul>');
        return formatted;
    }
});
