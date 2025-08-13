# MamaOpe AI Diagnosis Chat Interface

A simple web interface for the MamaOpe AI diagnostic system.

## Features

- 💬 Clean chat interface
- 🏥 Medical-themed design
- 📱 Responsive layout
- 🔄 Real-time API communication
- 📚 Formatted diagnostic responses with source references

## How to Use

1. **Start the Backend API**
   ```bash
   # Make sure your Docker container is running
   docker-compose up -d
   ```

2. **Open the Frontend**
   ```bash
   # Navigate to the frontend directory
   cd frontend
   
   # Open index.html in your browser
   open index.html
   # OR start a simple HTTP server
   python -m http.server 8080
   # Then visit: http://localhost:8080
   ```

3. **Enter Patient Cases**
   Type patient information in the chat box:
   ```
   Patient: 3-year-old child
   Symptoms: Persistent cough for 2 weeks, fever, difficulty breathing
   Vital signs: Temperature 38.5°C, HR 120 bpm, RR 35/min
   ```

4. **Review AI Responses**
   The system will provide:
   - 🤔 Questions (if more info needed)
   - 🔍 Clinical Impressions
   - 📋 Management Recommendations
   - 📚 Knowledge Base Sources
   - 🚨 Alerts (for critical conditions)

## Features

- **Enter key** to send messages
- **Auto-scrolling** chat
- **Loading indicators** during API calls
- **Error handling** for failed requests
- **Source attribution** from knowledge base
- **Chat history** maintained across conversation

## Requirements

- Backend API running on `http://localhost:8090`
- Modern web browser with JavaScript enabled 