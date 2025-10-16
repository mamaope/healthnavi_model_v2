
const API_URL = 'http://localhost:8050';
let chatHistory = [];

let accessToken = null;

// Overlay auth UI logic
window.showLoginOverlay = function() {
    document.getElementById('loginOverlay').style.display = 'flex';
    document.getElementById('registerOverlay').style.display = 'none';
    // Autofocus username
    setTimeout(() => {
        const input = document.getElementById('loginUsername');
        if (input) input.focus();
    }, 100);
}
window.showRegisterOverlay = function() {
    document.getElementById('registerOverlay').style.display = 'flex';
    document.getElementById('loginOverlay').style.display = 'none';
    setTimeout(() => {
        const input = document.getElementById('registerUsername');
        if (input) input.focus();
    }, 100);
}
window.closeAuthOverlay = function() {
    document.getElementById('loginOverlay').style.display = 'none';
    document.getElementById('registerOverlay').style.display = 'none';
}

// Registration handler
window.registerUser = async function(event) {
    event.preventDefault();
    const username = document.getElementById('registerUsername').value.trim();
    const fullName = document.getElementById('registerFullName').value.trim();
    const email = document.getElementById('registerEmail').value.trim();
    const password = document.getElementById('registerPassword').value;
    const errorDiv = document.getElementById('registerError');
    const successDiv = document.getElementById('registerSuccess');
    errorDiv.textContent = '';
    successDiv.textContent = '';
    try {
        const res = await fetch(`${API_URL}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, full_name: fullName, email, password })
        });
        if (!res.ok) {
            const data = await res.json();
            throw new Error(data.detail || 'Registration failed');
        }
        successDiv.textContent = 'Registration successful! You can now log in.';
        document.getElementById('registerForm').reset();
        // Optionally, auto-switch to login overlay
        setTimeout(() => {
            showLoginOverlay();
        }, 1200);
    } catch (err) {
        errorDiv.textContent = err.message;
    }
}

// Login handler
window.loginUser = async function(event) {
    event.preventDefault();
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    const errorDiv = document.getElementById('loginError');
    errorDiv.textContent = '';
    try {
        const res = await fetch(`${API_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        if (!res.ok) {
            const data = await res.json();
            throw new Error(data.detail || 'Login failed');
        }
        const data = await res.json();
        accessToken = data.access_token;
        // Enable chat input and hide auth actions
        document.getElementById('messageInput').disabled = false;
        document.getElementById('sendButton').disabled = false;
        document.getElementById('authActions').style.display = 'none';
        closeAuthOverlay();
        // Optionally, clear login form
        document.getElementById('loginForm').reset();
    } catch (err) {
        errorDiv.textContent = err.message;
    }
}

// Initialize chat
document.addEventListener('DOMContentLoaded', function() {
    const messageInput = document.getElementById('messageInput');
    
    // Auto-resize textarea - ensure all text is visible
    messageInput.addEventListener('input', function() {
        // Reset height to auto to get the correct scrollHeight
        this.style.height = 'auto';
        
        // Calculate the required height based on content
        const scrollHeight = this.scrollHeight;
        const minHeight = 24;
        const maxHeight = 120;
        
        // Set height to show all content, respecting min/max bounds
        const newHeight = Math.max(minHeight, Math.min(scrollHeight, maxHeight));
        this.style.height = newHeight + 'px';
        
        // If content exceeds max height, show scrollbar
        if (scrollHeight > maxHeight) {
            this.style.overflowY = 'auto';
        } else {
            this.style.overflowY = 'hidden';
        }
    });
    
    // Enter key to send message
    messageInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Ensure proper sizing when focused
    messageInput.addEventListener('focus', function() {
        if (this.value) {
            this.style.height = 'auto';
            this.style.height = Math.max(24, Math.min(this.scrollHeight, 120)) + 'px';
        }
    });
    
    // Initial height setup
    messageInput.style.height = 'auto';
    messageInput.style.height = messageInput.scrollHeight + 'px';
});

async function sendMessage() {
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    
    const message = messageInput.value.trim();
    if (!message) return;
    

    // If not authenticated, do nothing
    if (!accessToken) {
        addMessage('error', 'You must be logged in to send messages.');
        return;
    }
    // Disable input and show loading
    messageInput.disabled = true;
    sendButton.disabled = true;
    sendButton.innerHTML = '<div class="spinner"></div>';
    
    // Add user message to chat
    addMessage('user', message);
    console.log('✅ User message added to DOM');
    messageInput.value = '';
    messageInput.style.height = 'auto';
    messageInput.style.height = '24px'; // Reset to minimum height
    messageInput.style.overflowY = 'hidden'; // Reset overflow
    
    try {
        // Prepare API request
        const requestBody = {
            patient_data: message,
            chat_history: formatChatHistory()
        };
        
        // Call diagnosis API with streaming
        const headers = { 'Content-Type': 'application/json' };
        if (accessToken) {
            headers['Authorization'] = `Bearer ${accessToken}`;
        }
        
        console.log('🚀 Starting fetch request...');
        const response = await fetch(`${API_URL}/api/v2/diagnose`, {
            method: 'POST',
            headers,
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        console.log('✅ Response received, starting to process stream...');
        
        // Create AI message container IMMEDIATELY for streaming with typing indicator
        const chatMessages = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai-message';
        const uniqueId = `streaming-response-${Date.now()}`;
        messageDiv.innerHTML = `
            <div class="message-content">
                <div id="${uniqueId}"><span class="typing-indicator">●●●</span></div>
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        console.log('✅ AI message container added to DOM');
        
        const responseContainer = document.getElementById(uniqueId);
        
        // Handle streaming response with proper chunk processing
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        let chunkCount = 0;
        let lastRenderTime = Date.now();
        const renderInterval = 100; // Update UI every 100ms for smooth streaming feel
        
        // Read and display stream chunks in real-time
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
                console.log(`✅ Stream complete! Received ${chunkCount} chunks, ${fullResponse.length} total chars`);
                break;
            }
            
            // Decode chunk incrementally
            const chunk = decoder.decode(value, { stream: true });
            chunkCount++;
            
            if (chunkCount === 1) {
                console.log('⚡ First chunk received!');
            }
            
            fullResponse += chunk;
            
            // Throttle rendering for performance (update every 100ms or on first chunk)
            const now = Date.now();
            if (chunkCount === 1 || now - lastRenderTime >= renderInterval) {
                // Use textContent for instant raw display (much faster than HTML formatting)
                responseContainer.textContent = fullResponse;
                lastRenderTime = now;
                
                // Auto-scroll to bottom
                window.scrollTo({
                    top: document.body.scrollHeight,
                    behavior: 'smooth'
                });
            }
        }
        
        // Final formatting after stream completes (apply markdown/HTML formatting)
        console.log('🎨 Applying final formatting...');
        responseContainer.innerHTML = formatAIResponse(fullResponse);
        
        // Update chat history with complete response
        chatHistory.push({
            user: message,
            ai: fullResponse
        });
        
    } catch (error) {
        console.error('❌ Error:', error);
        addMessage('error', `Sorry, there was an error processing your request: ${error.message}`);
    } finally {
        // Re-enable input
        messageInput.disabled = false;
        sendButton.disabled = false;
        sendButton.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m22 2-7 20-4-9-9-4 20-7z"></path></svg>';
        messageInput.focus();
    }
}

function addMessage(type, content, diagnosisComplete = false) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    
    if (type === 'user') {
        messageDiv.innerHTML = `
            <div class="message-content">
                ${formatUserMessage(content)}
            </div>
        `;
    } else if (type === 'ai') {
        messageDiv.innerHTML = `
            <div class="message-content">
                ${formatAIResponse(content)}
            </div>
        `;
    } else if (type === 'error') {
        messageDiv.innerHTML = `
            <div class="message-content">
                <strong>⚠️ Error:</strong><br>
                ${content}
            </div>
        `;
    }
    
    chatMessages.appendChild(messageDiv);
    
    // Smooth scroll to the new message using window scroll
    setTimeout(() => {
        window.scrollTo({
            top: document.body.scrollHeight,
            behavior: 'smooth'
        });
    }, 100);
    
    // Remove welcome message after first interaction
    const welcomeMessage = chatMessages.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }
}

function formatUserMessage(message) {
    return message.replace(/\n/g, '<br>');
}

function formatAIResponse(response) {
    // Check if it's a differential diagnosis response
    if (response.includes('**DIFFERENTIAL DIAGNOSIS**')) {
        return formatDifferentialDiagnosis(response);
    }
    
    // Default formatting for other responses
    let formattedResponse = response;
    
    // Format sections with proper headers
    formattedResponse = formattedResponse
        .replace(/\*\*Question:\*\*/g, '<h4>Question:</h4>')
        .replace(/\*\*Rationale:\*\*/g, '<h4> Rationale:</h4>')
        .replace(/\*\*Impression:\*\*/g, '<h4> Clinical Impression:</h4>')
        .replace(/\*\*Further Management:\*\*/g, '<h4> Further Management:</h4>')
        .replace(/\*\*Sources:\*\*/g, '<h4> Knowledge Base Sources:</h4>')
        .replace(/\*\*ALERT:\*\*/g, '<h4 style="color: #dc3545;"> ALERT:</h4>');
    
    // Format numbered lists
    formattedResponse = formattedResponse.replace(/(\d+\.)\s/g, '<br><strong>$1</strong> ');
    
    // Format bullet points
    formattedResponse = formattedResponse.replace(/^- /gm, '• ');
    
    // Format line breaks
    formattedResponse = formattedResponse.replace(/\n/g, '<br>');
    
    // Highlight the disclaimer
    formattedResponse = formattedResponse.replace(
        /\*(.*application is for clinical decision support.*)\*/,
        '<div class="disclaimer">$1</div>'
    );
    
    return formattedResponse;
}

function formatDifferentialDiagnosis(response) {
    // Extract the main title
    const mainTitle = response.match(/\*\*DIFFERENTIAL DIAGNOSIS\*\*/)?.[0] || '**DIFFERENTIAL DIAGNOSIS**';
    
    // Extract case discussion
    const caseDiscussionMatch = response.match(/\*\*Case Discussion:\*\*([\s\S]*?)(?=\*\*Most Likely Diagnoses:\*\*|\*\*Expanded Differential:\*\*|$)/);
    const caseDiscussion = caseDiscussionMatch ? caseDiscussionMatch[1].trim() : '';
    
    // Extract most likely diagnoses
    const mostLikelyMatch = response.match(/\*\*Most Likely Diagnoses:\*\*([\s\S]*?)(?=\*\*Expanded Differential:\*\*|$)/);
    const mostLikely = mostLikelyMatch ? mostLikelyMatch[1].trim() : '';
    
    // Extract expanded differential
    const expandedMatch = response.match(/\*\*Expanded Differential:\*\*([\s\S]*?)(?=\*\*Sources:\*\*|$)/);
    const expanded = expandedMatch ? expandedMatch[1].trim() : '';
    
    // Extract sources
    const sourcesMatch = response.match(/\*\*Sources:\*\*([\s\S]*?)(?=\*This application.*|$)/);
    const sources = sourcesMatch ? sourcesMatch[1].trim() : '';
    
    // Extract disclaimer
    const disclaimerMatch = response.match(/\*This application.*\*/);
    const disclaimer = disclaimerMatch ? disclaimerMatch[0] : '';
    
    let formattedHTML = `
        <div class="diagnosis-card">
            <h3>${mainTitle.replace(/\*\*/g, '')}</h3>
    `;
    
    if (caseDiscussion) {
        formattedHTML += `
            <div class="case-discussion">
                <h4>Case Discussion</h4>
                <p>${formatText(caseDiscussion)}</p>
            </div>
        `;
    }
    
    if (mostLikely) {
        formattedHTML += `
            <div class="diagnosis-list">
                <h4>Most Likely Diagnoses</h4>
                ${formatDiagnosisList(mostLikely)}
            </div>
        `;
    }
    
    if (expanded) {
        formattedHTML += `
            <div class="diagnosis-list">
                <h4>Expanded Differential</h4>
                ${formatDiagnosisList(expanded)}
            </div>
        `;
    }
    
    if (sources) {
        formattedHTML += `
            <div class="sources">
                <strong>Sources:</strong> ${formatText(sources)}
            </div>
        `;
    }
    
    if (disclaimer) {
        formattedHTML += `
            <div class="disclaimer">
                ${disclaimer.replace(/\*/g, '')}
            </div>
        `;
    }
    
    formattedHTML += '</div>';
    
    return formattedHTML;
}

function formatDiagnosisList(text) {
    // Split by bullet points or numbered items
    const items = text.split(/(?=^- |^-\s|\d+\.\s)/).filter(item => item.trim());
    
    if (items.length > 0) {
        let html = '<ul>';
        items.forEach(item => {
            if (item.trim()) {
                html += `<li>${formatText(item.replace(/^[-•\d\.\s]+/, ''))}</li>`;
            }
        });
        html += '</ul>';
        return html;
    }
    
    return `<p>${formatText(text)}</p>`;
}

function formatText(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`\[Source: (.*?)\]`/g, '<em>[Source: $1]</em>')
        .replace(/\n/g, '<br>')
        .trim();
}

function formatChatHistory() {
    if (chatHistory.length === 0) return '';
    
    return chatHistory.map(entry => 
        `Doctor: ${entry.user}\nModel: ${entry.ai}`
    ).join('\n\n');
}

// Clear chat function
function clearChat() {
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.innerHTML = `
        <div class="welcome-message">
            <p>How can I help you?</p>
            <div class="sample-case">
                <button onclick="loadSampleCase()" class="sample-btn">
                    Try Sample Case
                </button>
            </div>
        </div>
    `;
    chatHistory = [];
}

// Load sample case for testing
function loadSampleCase() {
    const messageInput = document.getElementById('messageInput');
    messageInput.value = "Draft a differential diagnosis for a 65-year-old woman with history of diabetes and hyperlipidemia presents with acute-onset chest pain and diaphoresis found to have hyperacute T-waves without ST elevation.";
    messageInput.focus();
}


// Add spinner styles (if not already present)
if (!document.getElementById('spinner-style')) {
    const style = document.createElement('style');
    style.id = 'spinner-style';
    style.textContent = `
        .spinner {
            width: 16px;
            height: 16px;
            border: 2px solid #ffffff;
            border-top: 2px solid transparent;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);
}

// On load, ensure chat input is disabled and auth actions are visible
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('messageInput').disabled = true;
    document.getElementById('sendButton').disabled = true;
    document.getElementById('authActions').style.display = '';
    // Allow pressing Enter to submit login/register forms
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                loginUser(e);
            }
        });
    }
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                registerUser(e);
            }
        });
    }
});