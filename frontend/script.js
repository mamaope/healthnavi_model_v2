// Modern JavaScript for HealthNavi AI - Inspired by Glass Health and OpenEvidence
const API_URL = 'http://localhost:8050/api/v2';
let chatHistory = [];
let accessToken = null;
let currentUser = null;
let isAuthenticated = false;
let currentSession = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    setupEventListeners();
    checkAuthentication();
});

function initializeApp() {
    // Set up message input auto-resize for landing page
    const landingMessageInput = document.getElementById('landingMessageInput');
    const landingSendButton = document.getElementById('landingSendButton');
    
    // Landing page input
    if (landingMessageInput) {
        landingMessageInput.addEventListener('input', autoResizeTextarea);
        landingMessageInput.addEventListener('keydown', handleKeyDown);
    }
    
    // Initially disable send button
    if (landingSendButton) {
        landingSendButton.disabled = true;
    }
    
    // Set up chat expansion observer
    setupChatExpansionObserver();
}

function setupEventListeners() {
    // Auth form submission
    const authForm = document.getElementById('authForm');
    if (authForm) {
        authForm.addEventListener('submit', handleAuthSubmit);
    }
    
    // Modal close on outside click
    const modal = document.getElementById('authModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeAuthModal();
            }
        });
    }
}

function setupChatExpansionObserver() {
    const chatMessages = document.getElementById('landingChatMessages');
    const chatContainer = document.querySelector('.chat-container');
    if (!chatMessages || !chatContainer) return;
    
    // Initially center the chat
    chatContainer.classList.add('centered');
    
    // Expand chat area when messages are added
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                // Check if welcome message was removed
                const welcomeMessage = chatMessages.querySelector('.welcome-message');
                if (!welcomeMessage) {
                    chatContainer.classList.remove('centered');
                    chatMessages.style.justifyContent = 'flex-start';
                    chatMessages.style.paddingTop = 'var(--spacing-md)';
                }
            }
        });
    });
    
    observer.observe(chatMessages, { childList: true, subtree: true });
}

function checkAuthentication() {
    // Check for stored token
    const storedToken = localStorage.getItem('accessToken');
    const storedUser = localStorage.getItem('currentUser');
    
    if (storedToken && storedUser) {
        try {
            accessToken = storedToken;
            currentUser = JSON.parse(storedUser);
            isAuthenticated = true;
            updateAuthenticationUI(true);
        } catch (error) {
            console.error('Error parsing stored user data:', error);
            clearStoredAuth();
        }
    } else {
        updateAuthenticationUI(false);
    }
}

function updateAuthenticationUI(authenticated) {
    const landingPage = document.getElementById('landingPage');
    const chatContainer = document.querySelector('.chat-container');
    
    if (authenticated) {
        // For authenticated users, show the same UI but enable full functionality
        if (landingPage) landingPage.style.display = 'flex';
        
        // Update user info
        updateUserInfo();
        
        // Load user sessions if needed
        if (typeof loadUserSessions === 'function') {
            loadUserSessions();
        }
    } else {
        // Show unauthenticated UI
        if (landingPage) landingPage.style.display = 'flex';
        
        // Center chat for unauthenticated users
        if (chatContainer) {
            chatContainer.classList.add('centered');
        }
        
        // Clear any existing chat
        clearChat();
    }
}

function updateUserInfo() {
    if (currentUser) {
        const userName = document.getElementById('userName');
        const userEmail = document.getElementById('userEmail');
        
        if (userName) userName.textContent = currentUser.full_name || currentUser.username;
        if (userEmail) userEmail.textContent = currentUser.email;
    }
}

// Authentication Modal Functions
function showAuthModal(mode) {
    const modal = document.getElementById('authModal');
    const modalTitle = document.getElementById('modalTitle');
    const submitBtn = document.getElementById('submitBtn');
    const confirmPasswordGroup = document.getElementById('confirmPasswordGroup');
    const fullNameGroup = document.getElementById('fullNameGroup');
    const modalFooterText = document.getElementById('modalFooterText');
    
    if (mode === 'login') {
        modalTitle.textContent = 'Sign In';
        submitBtn.textContent = 'Sign In';
        confirmPasswordGroup.style.display = 'none';
        fullNameGroup.style.display = 'none';
        modalFooterText.innerHTML = 'Don\'t have an account? <a href="#" onclick="toggleAuthMode()">Sign up</a>';
    } else {
        modalTitle.textContent = 'Create Account';
        submitBtn.textContent = 'Sign Up';
        confirmPasswordGroup.style.display = 'block';
        fullNameGroup.style.display = 'block';
        modalFooterText.innerHTML = 'Already have an account? <a href="#" onclick="toggleAuthMode()">Sign in</a>';
    }
    
    modal.classList.add('show');
    document.body.style.overflow = 'hidden';
    
    // Focus first input
    setTimeout(() => {
        const firstInput = modal.querySelector('input');
        if (firstInput) firstInput.focus();
    }, 100);
}

function closeAuthModal() {
    const modal = document.getElementById('authModal');
    modal.classList.remove('show');
    document.body.style.overflow = '';
    
    // Clear form
    const form = document.getElementById('authForm');
    if (form) form.reset();
}

function toggleAuthMode() {
    const modalTitle = document.getElementById('modalTitle');
    const isLogin = modalTitle.textContent === 'Sign In';
    showAuthModal(isLogin ? 'register' : 'login');
}

async function handleAuthSubmit(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const email = formData.get('email');
    const password = formData.get('password');
    const confirmPassword = formData.get('confirmPassword');
    const fullName = formData.get('fullName');
    
    const submitBtn = document.getElementById('submitBtn');
    const isLogin = submitBtn.textContent === 'Sign In';
    
    // Client-side validation
    if (!email || !password) {
        showAuthError('Email and password are required');
        return;
    }
    
    if (!isLogin) {
        if (!fullName) {
            showAuthError('Full name is required');
            return;
        }
        if (password !== confirmPassword) {
            showAuthError('Passwords do not match');
            return;
        }
        if (password.length < 8) {
            showAuthError('Password must be at least 8 characters long');
            return;
        }
    }
    
    // Show loading state
    submitBtn.disabled = true;
    submitBtn.textContent = isLogin ? 'Signing In...' : 'Creating Account...';
    
    try {
        if (isLogin) {
            await loginUser(email, password);
        } else {
            await registerUser(fullName, email, password);
        }
    } catch (error) {
        console.error('Auth error:', error);
        showAuthError(error.message || 'An error occurred. Please try again.');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = isLogin ? 'Sign In' : 'Sign Up';
    }
}

async function loginUser(email, password) {
    const response = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
        body: JSON.stringify({ email, password })
    });
    
    const data = await response.json();
    
    if (data.success) {
        accessToken = data.data.access_token;
        currentUser = data.data.user;
        isAuthenticated = true;
        
        // Store in localStorage
        localStorage.setItem('accessToken', accessToken);
        localStorage.setItem('currentUser', JSON.stringify(currentUser));
        
        // Update UI
        updateAuthenticationUI(true);
        closeAuthModal();
        
        // Show welcome message
        addMessage('ai', `Welcome back, ${currentUser.full_name || currentUser.username}! How can I help you today?`);
    } else {
        const errorMessage = data.metadata?.errors?.join(', ') || data.data?.message || 'Login failed';
        throw new Error(errorMessage);
    }
}

async function registerUser(fullName, email, password) {
    const response = await fetch(`${API_URL}/auth/register`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
        body: JSON.stringify({
            full_name: fullName,
            email: email,
            password: password
        })
    });
    
    const data = await response.json();
    
    if (data.success) {
        // Registration successful, switch to login
        showAuthError('Registration successful! Please sign in with your credentials.', 'success');
        setTimeout(() => {
            showAuthModal('login');
        }, 2000);
    } else {
        const errorMessage = data.metadata?.errors?.join(', ') || data.data?.message || 'Registration failed';
        throw new Error(errorMessage);
    }
}

function showAuthError(message, type = 'error') {
    // Remove existing error messages
    const existingError = document.querySelector('.auth-error');
    if (existingError) existingError.remove();
    
    // Create new error message
    const errorDiv = document.createElement('div');
    errorDiv.className = `auth-error ${type}`;
    errorDiv.textContent = message;
    errorDiv.style.color = type === 'success' ? '#059669' : '#dc2626';
    errorDiv.style.fontSize = '0.875rem';
    errorDiv.style.marginTop = '0.5rem';
    
    // Insert after form
    const form = document.getElementById('authForm');
    form.parentNode.insertBefore(errorDiv, form.nextSibling);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (errorDiv.parentNode) {
            errorDiv.remove();
        }
    }, 5000);
}

function logout() {
    accessToken = null;
    currentUser = null;
    isAuthenticated = false;
    currentSession = null;
    
    // Clear localStorage
    clearStoredAuth();
    
    // Update UI
    updateAuthenticationUI(false);
    
    // Show signup prompt
    showAuthModal('login');
}

function clearStoredAuth() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('currentUser');
}

// Message Functions
async function sendMessage() {
    // Get the input and button
    const messageInput = document.getElementById('landingMessageInput');
    const sendButton = document.getElementById('landingSendButton');
    
    if (!messageInput) {
        console.error('No message input found');
        return;
    }
    
    const message = messageInput.value.trim();
    if (!message) return;
    
    console.log('🚀 [Frontend] sendMessage called');
    console.log('   Message:', message);
    console.log('   Authenticated:', isAuthenticated);
    console.log('   Access token:', accessToken ? 'Present' : 'Missing');
    
    // Check authentication
    if (!isAuthenticated) {
        console.log('🔐 [Frontend] Not authenticated, showing auth modal');
        showAuthModal('register');
        return;
    }
    
    // Disable input and show loading
    messageInput.disabled = true;
    sendButton.disabled = true;
    sendButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    
    // Add user message to chat
    addMessage('user', message);
    messageInput.value = '';
    autoResizeTextarea.call(messageInput);
    
    try {
        // Create or get current session
        if (!currentSession) {
            console.log('📝 [Frontend] Creating new session');
            currentSession = await createSession();
            if (currentSession) {
                // Refresh the sessions list to show the new session
                loadUserSessions();
            }
        }
        
        console.log('🔵 [Frontend] Sending diagnosis request');
        console.log('   Session ID:', currentSession?.id);
        console.log('   Chat history:', formatChatHistory());
        
        // Send message to API
        const response = await fetch(`${API_URL}/diagnosis/diagnose`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify({
                patient_data: message,
                chat_history: formatChatHistory(),
                session_id: currentSession.id
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        console.log('🔵 [Frontend] Diagnosis response received:', data);
        
        // Check if response has the expected structure
        if (!data.data) {
            throw new Error('Invalid response structure: missing data field');
        }
        
        // Add AI response to chat
        addMessage('ai', data.data.model_response, data.data.diagnosis_complete);
        
        // Update chat history
        chatHistory.push({
            user: message,
            ai: data.data.model_response
        });
        
    } catch (error) {
        console.error('Error:', error);
        addMessage('error', `Sorry, there was an error processing your request: ${error.message}`);
    } finally {
        // Re-enable input
        messageInput.disabled = false;
        sendButton.disabled = false;
        sendButton.innerHTML = '<i class="fas fa-paper-plane"></i>';
        messageInput.focus();
    }
}

function addMessage(type, content, diagnosisComplete = false) {
    console.log('💬 [Frontend] addMessage called:', { type, content: content.substring(0, 100) + '...', diagnosisComplete });
    
    // Get the chat container
    const chatMessages = document.getElementById('landingChatMessages');
    
    console.log('💬 [Frontend] Chat container found:', !!chatMessages);
    
    if (!chatMessages) {
        console.error('No chat messages container found');
        return;
    }
    
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
    console.log('💬 [Frontend] Message added to chat container');
    
    // Smooth scroll to the new message
    setTimeout(() => {
        messageDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
    
    // Remove welcome message after first interaction
    const welcomeMessage = chatMessages.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
        console.log('💬 [Frontend] Welcome message removed');
    }
}

function formatUserMessage(message) {
    return message.replace(/\n/g, '<br>');
}

function formatAIResponse(response) {
    console.log('🎨 [Frontend] Formatting AI response:', response.substring(0, 200) + '...');
    
    // Check if it's a JSON response (new format)
    if (response.trim().startsWith('{') && response.trim().endsWith('}')) {
        return formatJSONResponse(response);
    }
    
    // Check if it's a differential diagnosis response
    if (response.includes('**DIFFERENTIAL DIAGNOSIS**')) {
        return formatDifferentialDiagnosis(response);
    }
    
    // Enhanced markdown formatting
    let formattedResponse = response;
    
    // Remove any existing HTML tags that might be in the response
    formattedResponse = formattedResponse.replace(/<[^>]*>/g, '');
    
    // Format headers (## and ###)
    formattedResponse = formattedResponse
        .replace(/^### (.*$)/gm, '<h4>$1</h4>')
        .replace(/^## (.*$)/gm, '<h3>$1</h3>')
        .replace(/^# (.*$)/gm, '<h2>$1</h2>');
    
    // Format bold text (**text** or __text__)
    formattedResponse = formattedResponse
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/__(.*?)__/g, '<strong>$1</strong>');
    
    // Format italic text (*text* or _text_)
    formattedResponse = formattedResponse
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/_(.*?)_/g, '<em>$1</em>');
    
    // Format code blocks (```code```)
    formattedResponse = formattedResponse
        .replace(/```([\s\S]*?)```/g, '<pre class="code-block"><code>$1</code></pre>');
    
    // Format inline code (`code`)
    formattedResponse = formattedResponse
        .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    
    // Format links [text](url)
    formattedResponse = formattedResponse
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    
    // Format medical sections with icons
    formattedResponse = formattedResponse
        .replace(/\*\*Question:\*\*/g, '<h4>📋 Question:</h4>')
        .replace(/\*\*Rationale:\*\*/g, '<h4>🧠 Rationale:</h4>')
        .replace(/\*\*Impression:\*\*/g, '<h4>💡 Clinical Impression:</h4>')
        .replace(/\*\*Further Management:\*\*/g, '<h4>⚕️ Further Management:</h4>')
        .replace(/\*\*Sources:\*\*/g, '<h4>📚 Knowledge Base Sources:</h4>')
        .replace(/\*\*ALERT:\*\*/g, '<h4 style="color: #dc3545;">🚨 ALERT:</h4>')
        .replace(/\*\*Clinical Overview:\*\*/g, '<h4>🏥 Clinical Overview:</h4>')
        .replace(/\*\*Differential Diagnoses:\*\*/g, '<h4>🔍 Differential Diagnoses:</h4>')
        .replace(/\*\*Immediate Workup:\*\*/g, '<h4>🔬 Immediate Workup:</h4>')
        .replace(/\*\*Management:\*\*/g, '<h4>💊 Management:</h4>')
        .replace(/\*\*Red Flags:\*\*/g, '<h4 style="color: #dc3545;">🚩 Red Flags:</h4>');
    
    // Format numbered lists (1. 2. 3.)
    formattedResponse = formattedResponse.replace(/^(\d+)\.\s+(.*)$/gm, '<div class="numbered-item"><span class="number">$1.</span> $2</div>');
    
    // Format bullet points (- or *)
    formattedResponse = formattedResponse.replace(/^[-*]\s+(.*)$/gm, '<div class="bullet-item">• $1</div>');
    
    // Format blockquotes (> text)
    formattedResponse = formattedResponse.replace(/^>\s+(.*)$/gm, '<blockquote>$1</blockquote>');
    
    // Format horizontal rules (--- or ***)
    formattedResponse = formattedResponse.replace(/^[-*]{3,}$/gm, '<hr>');
    
    // Format line breaks and paragraphs properly
    // First, protect existing HTML elements
    const protectedElements = [];
    formattedResponse = formattedResponse.replace(/<[^>]+>/g, (match) => {
        protectedElements.push(match);
        return `__PROTECTED_${protectedElements.length - 1}__`;
    });
    
    // Split into lines and process each line
    const lines = formattedResponse.split('\n');
    const processedLines = [];
    let inList = false;
    let inCodeBlock = false;
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        
        // Skip empty lines
        if (!line) {
            processedLines.push('');
            continue;
        }
        
        // Check for headers (already processed above)
        if (line.startsWith('<h')) {
            processedLines.push(line);
            continue;
        }
        
        // Check for list items (already processed above)
        if (line.startsWith('<div class="numbered-item">') || line.startsWith('<div class="bullet-item">')) {
            if (!inList) {
                inList = true;
            }
            processedLines.push(line);
            continue;
        } else if (inList) {
            inList = false;
        }
        
        // Check for blockquotes (already processed above)
        if (line.startsWith('<blockquote>')) {
            processedLines.push(line);
            continue;
        }
        
        // Check for horizontal rules (already processed above)
        if (line.startsWith('<hr>')) {
            processedLines.push(line);
            continue;
        }
        
        // Check for code blocks
        if (line.startsWith('<pre class="code-block">')) {
            inCodeBlock = true;
            processedLines.push(line);
            continue;
        } else if (inCodeBlock && line.includes('</pre>')) {
            inCodeBlock = false;
            processedLines.push(line);
            continue;
        } else if (inCodeBlock) {
            processedLines.push(line);
            continue;
        }
        
        // Regular paragraph content
        processedLines.push(`<p>${line}</p>`);
    }
    
    // Join lines and restore protected elements
    formattedResponse = processedLines.join('\n');
    protectedElements.forEach((element, index) => {
        formattedResponse = formattedResponse.replace(`__PROTECTED_${index}__`, element);
    });
    
    // Clean up empty paragraphs
    formattedResponse = formattedResponse.replace(/<p><\/p>/g, '');
    formattedResponse = formattedResponse.replace(/<p>\s*<\/p>/g, '');
    
    // Clean up multiple consecutive line breaks
    formattedResponse = formattedResponse.replace(/\n{3,}/g, '\n\n');
    
    // Highlight disclaimers
    formattedResponse = formattedResponse.replace(
        /(This application is for clinical decision support.*?\.)/gi,
        '<div class="disclaimer">$1</div>'
    );
    
    // Format probability percentages
    formattedResponse = formattedResponse.replace(
        /(\d+)%/g,
        '<span class="probability-badge">$1%</span>'
    );
    
    return formattedResponse;
}

function formatJSONResponse(response) {
    try {
        const data = JSON.parse(response);
        console.log('🎨 [Frontend] Parsing JSON response:', data);
        
        let html = '<div class="diagnosis-card">';
        
        // Clinical Overview
        if (data.clinical_overview) {
            html += `
                <h3>🏥 Clinical Assessment</h3>
                <div class="case-discussion">
                    <p>${data.clinical_overview}</p>
                </div>
            `;
        }
        
        // Critical Alert
        if (data.critical_alert) {
            html += `
                <div class="critical-alert">
                    <h4 style="color: #dc3545;">🚨 CRITICAL ALERT</h4>
                    <p>This case requires immediate attention and urgent intervention.</p>
                </div>
            `;
        }
        
        // Differential Diagnoses
        if (data.differential_diagnoses && data.differential_diagnoses.length > 0) {
            html += `
                <div class="differential-diagnoses-section">
                    <h4>🔍 Differential Diagnoses</h4>
                    <div class="diagnoses-grid">
            `;
            
            // Sort diagnoses by probability (highest first)
            const sortedDiagnoses = data.differential_diagnoses.sort((a, b) => 
                (b.probability_percent || 0) - (a.probability_percent || 0)
            );
            
            sortedDiagnoses.forEach((diagnosis, index) => {
                const probability = diagnosis.probability_percent || 0;
                const probabilityColor = probability >= 70 ? '#dc3545' : probability >= 40 ? '#fd7e14' : '#28a745';
                const probabilityText = probability >= 70 ? 'High' : probability >= 40 ? 'Moderate' : 'Low';
                const rank = index + 1;
                
                html += `
                    <div class="diagnosis-card-item">
                        <div class="diagnosis-rank">#${rank}</div>
                        <div class="diagnosis-content">
                            <div class="diagnosis-header">
                                <h5 class="diagnosis-title">${diagnosis.diagnosis}</h5>
                                <div class="probability-container">
                                    <span class="probability-badge" style="background: ${probabilityColor}">
                                        ${probability}%
                                    </span>
                                    <span class="probability-label">${probabilityText} Probability</span>
                                </div>
                            </div>
                            <div class="diagnosis-evidence">
                                <strong>Evidence:</strong> ${diagnosis.evidence}
                            </div>
                            ${diagnosis.citations && diagnosis.citations.length > 0 ? `
                                <div class="diagnosis-citations">
                                    <strong>📚 Sources:</strong> ${diagnosis.citations.join(', ')}
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            });
            
            html += `
                    </div>
                </div>
            `;
        }
        
        // Immediate Workup
        if (data.immediate_workup && data.immediate_workup.length > 0) {
            html += `
                <div class="workup-section">
                    <h4>⚕️ Immediate Workup</h4>
                    <ul>
            `;
            data.immediate_workup.forEach(item => {
                html += `<li>${item}</li>`;
            });
            html += `
                    </ul>
                </div>
            `;
        }
        
        // Management
        if (data.management && data.management.length > 0) {
            html += `
                <div class="management-section">
                    <h4>💊 Management</h4>
                    <ul>
            `;
            data.management.forEach(item => {
                html += `<li>${item}</li>`;
            });
            html += `
                    </ul>
                </div>
            `;
        }
        
        // Red Flags
        if (data.red_flags && data.red_flags.length > 0) {
            html += `
                <div class="red-flags-section">
                    <h4 style="color: #dc3545;">🚩 Red Flags</h4>
                    <ul>
            `;
            data.red_flags.forEach(flag => {
                html += `<li>${flag}</li>`;
            });
            html += `
                    </ul>
                </div>
            `;
        }
        
        // Additional Information Needed
        if (data.additional_information_needed) {
            html += `
                <div class="additional-info">
                    <h4>❓ Additional Information Needed</h4>
                    <p>${data.additional_information_needed}</p>
                </div>
            `;
        }
        
        // Sources
        if (data.sources_used && data.sources_used.length > 0) {
            html += `
                <div class="sources">
                    <strong>📚 Sources Used:</strong> ${data.sources_used.join(', ')}
                </div>
            `;
        }
        
        html += '</div>';
        return html;
        
    } catch (error) {
        console.error('Error parsing JSON response:', error);
        return `<div class="error-message">Error parsing AI response: ${error.message}</div>`;
    }
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

// Sample Question Functions
function useSamplePrompt(type) {
    const sampleQuestions = {
        'chest-pain': 'Adult patient presents with chest pain, shortness of breath, and diaphoresis. What are the differential diagnoses?',
        'fever': '5-year-old child with persistent high fever (39.5°C) for 3 days, no obvious cause. What should I consider?',
        'pediatric': 'Infant with respiratory distress, wheezing, and feeding difficulties. What are the possible causes?',
        'abdominal': 'Adult with acute severe abdominal pain, nausea, and vomiting. What diagnostic approach should I take?'
    };
    
    // Try dashboard input first, then landing input
    const dashboardInput = document.getElementById('dashboardMessageInput');
    const landingInput = document.getElementById('landingMessageInput');
    const messageInput = dashboardInput || landingInput;
    
    if (messageInput && sampleQuestions[type]) {
        messageInput.value = sampleQuestions[type];
        messageInput.focus();
        autoResizeTextarea.call(messageInput);
    }
}

// Session Management
async function createSession() {
    try {
        console.log('📝 [Frontend] Creating new chat session');
        const response = await fetch(`${API_URL}/chat/sessions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify({
                session_name: `Session ${new Date().toLocaleDateString()}`,
                patient_summary: ''
            })
        });
        
        const data = await response.json();
        console.log('📝 [Frontend] Session creation response:', data);
        
        if (data.success) {
            return data.data;
        } else {
            throw new Error('Failed to create session');
        }
    } catch (error) {
        console.error('Error creating session:', error);
        return null;
    }
}

async function loadUserSessions() {
    try {
        const response = await fetch(`${API_URL}/chat/sessions`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            updateSessionsList(data.data.sessions || data.data);
        }
    } catch (error) {
        console.error('Error loading sessions:', error);
    }
}

function updateSessionsList(sessions) {
    const sessionsList = document.getElementById('sessionsList');
    if (!sessionsList) return;
    
    sessionsList.innerHTML = '';
    
    sessions.forEach(session => {
        const sessionItem = document.createElement('div');
        sessionItem.className = 'session-item';
        sessionItem.innerHTML = `
            <div class="session-name">${session.session_name || `Session #${session.id}`}</div>
            <div class="session-date">${new Date(session.created_at).toLocaleDateString()}</div>
        `;
        
        sessionItem.addEventListener('click', () => {
            // Remove active class from all items
            document.querySelectorAll('.session-item').forEach(item => item.classList.remove('active'));
            // Add active class to clicked item
            sessionItem.classList.add('active');
            loadSession(session);
        });
        
        sessionsList.appendChild(sessionItem);
    });
}

async function loadSession(session) {
    console.log('📂 [Frontend] Loading session:', session);
    currentSession = session;
    
    try {
        // Load session messages
        const response = await fetch(`${API_URL}/chat/sessions/${session.id}/messages`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            }
        });
        
        const data = await response.json();
        console.log('📂 [Frontend] Session messages response:', data);
        
        if (data.success) {
            const messages = data.data.messages || [];
            console.log('📂 [Frontend] Loaded messages:', messages);
            
            // Clear current chat
            const dashboardChat = document.getElementById('dashboardChatMessages');
            const landingChat = document.getElementById('landingChatMessages');
            const chatMessages = dashboardChat || landingChat;
            
            if (chatMessages) {
                chatMessages.innerHTML = '';
            }
            
            // Add welcome message
            const welcomeDiv = document.createElement('div');
            welcomeDiv.className = 'welcome-message';
            welcomeDiv.innerHTML = `
                <div class="welcome-content">
                    <h3>Session: ${session.session_name || `Session #${session.id}`}</h3>
                    <p>Continuing previous conversation...</p>
                </div>
            `;
            if (chatMessages) {
                chatMessages.appendChild(welcomeDiv);
                
                // Add all messages from the session
                messages.forEach(message => {
                    const messageType = message.message_type === 'user' ? 'user' : 'ai';
                    addMessage(messageType, message.content, message.diagnosis_complete);
                });
                
                // Update chat history
                chatHistory = messages.map(msg => ({
                    user: msg.message_type === 'user' ? msg.content : null,
                    ai: msg.message_type === 'assistant' ? msg.content : null
                })).filter(msg => msg.user || msg.ai);
                
                // Scroll to bottom
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
            
        } else {
            console.error('Failed to load session messages');
        }
    } catch (error) {
        console.error('Error loading session:', error);
    }
}

function startNewSession() {
    currentSession = null;
    chatHistory = [];
    clearChat();
    
    // Update sidebar
    const sessionItems = document.querySelectorAll('.session-item');
    sessionItems.forEach(item => item.classList.remove('active'));
    
    console.log('🆕 [Frontend] Started new session - will create when first message is sent');
}

function clearChat() {
    // Clear chat container
    const landingChat = document.getElementById('landingChatMessages');
    
    const welcomeHTML = `
        <div class="welcome-message">
            <div class="welcome-content">
                <h1 class="welcome-logo">
                    <span class="logo-health">Health</span><span class="logo-navy">Navy</span>
                </h1>
                <h3>Welcome to HealthNavy</h3>
                <p>How can I assist you with your clinical decision support needs today?</p>
            </div>
        </div>
    `;
    
    if (landingChat) {
        landingChat.innerHTML = welcomeHTML;
    }
    
    chatHistory = [];
}

// Utility Functions
function autoResizeTextarea() {
    const textarea = this;
    
    textarea.style.height = 'auto';
    const scrollHeight = textarea.scrollHeight;
    const minHeight = 24;
    const maxHeight = 120;
    
    const newHeight = Math.max(minHeight, Math.min(scrollHeight, maxHeight));
    textarea.style.height = newHeight + 'px';
    
    if (scrollHeight > maxHeight) {
        textarea.style.overflowY = 'auto';
    } else {
        textarea.style.overflowY = 'hidden';
    }
    
    // Enable/disable send buttons based on input content
    const hasContent = textarea.value.trim().length > 0;
    
    const dashboardButton = document.getElementById('dashboardSendButton');
    const landingButton = document.getElementById('landingSendButton');
    
    if (dashboardButton) {
        dashboardButton.disabled = !hasContent;
    }
    if (landingButton) {
        landingButton.disabled = !hasContent;
    }
}

function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

// Global functions for HTML onclick handlers
window.showAuthModal = showAuthModal;
window.closeAuthModal = closeAuthModal;
window.toggleAuthMode = toggleAuthMode;
window.togglePasswordVisibility = togglePasswordVisibility;
window.sendMessage = sendMessage;
window.useSamplePrompt = useSamplePrompt;
window.logout = logout;
window.startNewSession = startNewSession;
window.showTerms = showTerms;
window.showPrivacy = showPrivacy;
window.showSupport = showSupport;

// Password visibility toggle function
function togglePasswordVisibility(inputId) {
    const input = document.getElementById(inputId);
    const toggle = input.parentElement.querySelector('.password-toggle i');
    
    if (input.type === 'password') {
        input.type = 'text';
        toggle.className = 'fas fa-eye-slash';
        toggle.setAttribute('aria-label', 'Hide password');
    } else {
        input.type = 'password';
        toggle.className = 'fas fa-eye';
        toggle.setAttribute('aria-label', 'Show password');
    }
}

// Footer link functions
function showTerms() {
    alert('Terms of Service: Please note that HealthNavy AI is designed for clinical decision support and should not replace professional medical judgment. All users must comply with applicable healthcare regulations and privacy requirements.');
}

function showPrivacy() {
    alert('Privacy Policy: Your medical information is protected and encrypted. We comply with HIPAA regulations and only process data necessary for providing clinical decision support.');
}

function showSupport() {
    alert('Support: For technical support or clinical assistance, please contact us at support@healthnavyai.com or visit our help center.');
}