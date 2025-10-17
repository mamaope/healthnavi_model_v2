# HealthNavi AI CDSS API Documentation

## Overview
HealthNavi AI CDSS is a Clinical Decision Support System powered by Google Vertex AI Gemini 2.5 Flash. The API provides authentication, user management, and AI-powered medical diagnosis assistance.

**Base URL:** `http://localhost:8050/api/v2`

## Authentication
The API uses JWT (JSON Web Token) authentication. Most endpoints require a valid JWT token in the Authorization header:
```
Authorization: Bearer <your-jwt-token>
```

## Response Format
All API responses follow a standardized format:

### Success Response
```json
{
  "data": {
    "message": "Success message",
    "details": {}
  },
  "metadata": {
    "statusCode": 200,
    "errors": [],
    "executionTime": 0.123,
    "timestamp": "2025-09-22T10:30:00.000000"
  },
  "success": 1
}
```

### Error Response
```json
{
  "data": {
    "message": "Error message",
    "details": null
  },
  "metadata": {
    "statusCode": 400,
    "errors": ["Error details"],
    "executionTime": 0.001,
    "timestamp": "2025-09-22T10:30:00.000000"
  },
  "success": 0
}
```

---

## Authentication Endpoints

### 1. User Registration
**POST** `/auth/register`

Register a new user account. Email verification is required before login.

**Request Body:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@example.com",
  "password": "SecurePass123!"
}
```

**Response:**
```json
{
  "data": {
    "message": "Registration successful. Please check your email for verification.",
    "details": {
      "user_id": 1,
      "email": "john.doe@example.com",
      "username": "john.doe.20250922103000123456"
    }
  },
  "metadata": {
    "statusCode": 201,
    "errors": [],
    "executionTime": 0.456,
    "timestamp": "2025-09-22T10:30:00.000000"
  },
  "success": 1
}
```

**Notes:**
- Username is automatically generated from first_name, last_name, and timestamp
- Email verification token is generated and sent to the provided email
- User must verify email before login

---

### 2. User Login
**POST** `/auth/login`

Authenticate user with email and password. Returns JWT token for subsequent requests.

**Request Body:**
```json
{
  "email": "john.doe@example.com",
  "password": "SecurePass123!"
}
```

**Response:**
```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "username": "john.doe.20250922103000123456",
      "email": "john.doe@example.com",
      "full_name": "John Doe",
      "role": "user",
      "is_active": true,
      "is_email_verified": true,
      "created_at": "2025-09-22T10:30:00.000000",
      "updated_at": "2025-09-22T10:30:00.000000"
    }
  },
  "metadata": {
    "statusCode": 200,
    "errors": [],
    "executionTime": 0.234,
    "timestamp": "2025-09-22T10:30:00.000000"
  },
  "success": 1
}
```

**Notes:**
- Returns JWT access token and complete user profile
- User profile includes all user information
- Token expires based on configuration (default: 30 minutes)

**Error Cases:**
- `400`: Invalid credentials
- `400`: Email not verified
- `400`: Account deactivated

---

### 3. Email Verification
**GET** `/auth/verify-email?token=<verification_token>`

Verify user email by clicking the link sent to their email.

**Query Parameters:**
- `token` (string, required): Email verification token

**Response:**
```json
{
  "data": {
    "message": "Email verified successfully"
  },
  "metadata": {
    "statusCode": 200,
    "errors": [],
    "executionTime": 0.123,
    "timestamp": "2025-09-22T10:30:00.000000"
  },
  "success": 1
}
```

**Notes:**
- This endpoint is designed for email links (GET requests)
- Users click the verification link in their email
- Token is automatically cleared after successful verification

---

### 4. Resend Verification Email
**POST** `/auth/resend-verification`

Resend email verification link to user's email.

**Request Body:**
```json
{
  "email": "john.doe@example.com"
}
```

**Response:**
```json
{
  "data": {
    "message": "Verification email sent successfully"
  },
  "metadata": {
    "statusCode": 200,
    "errors": [],
    "executionTime": 0.345,
    "timestamp": "2025-09-22T10:30:00.000000"
  },
  "success": 1
}
```

---

### 5. Get User Profile
**GET** `/auth/profile`

Get current user's profile information. Requires authentication.

**Headers:**
```
Authorization: Bearer <user-jwt-token>
```

**Response:**
```json
{
  "data": {
    "id": 1,
    "username": "john.doe.20250922103000123456",
    "email": "john.doe@example.com",
    "full_name": "John Doe",
    "role": "user",
    "is_active": true,
    "is_email_verified": true,
    "created_at": "2025-09-22T10:30:00.000000",
    "updated_at": "2025-09-22T10:30:00.000000"
  },
  "metadata": {
    "statusCode": 200,
    "errors": [],
    "executionTime": 0.123,
    "timestamp": "2025-09-22T10:30:00.000000"
  },
  "success": 1
}
```

**Notes:**
- Returns complete user profile information
- Requires valid JWT token
- Same data structure as user object in login response

---

### 6. Manual Email Verification (Development)
**POST** `/auth/manual-verify`

Manually verify email for development/testing purposes.

**Request Body:**
```json
"john.doe@example.com"
```

**Response:**
```json
{
  "data": {
    "message": "Email john.doe@example.com manually verified for development"
  },
  "metadata": {
    "statusCode": 200,
    "errors": [],
    "executionTime": 0.123,
    "timestamp": "2025-09-22T10:30:00.000000"
  },
  "success": 1
}
```

---

## User Management Endpoints (Admin Only)

### 7. Get All Users
**GET** `/auth/users`

Retrieve list of all users. Requires admin or super_admin role.

**Headers:**
```
Authorization: Bearer <admin-jwt-token>
```

**Query Parameters:**
- `skip` (integer, optional): Number of users to skip (default: 0)
- `limit` (integer, optional): Maximum number of users to return (default: 100)

**Response:**
```json
{
  "data": {
    "users": [
      {
        "id": 1,
        "username": "john.doe.20250922103000123456",
        "email": "john.doe@example.com",
        "full_name": "John Doe",
        "role": "user",
        "is_active": true,
        "is_email_verified": true,
        "created_at": "2025-09-22T10:30:00.000000",
        "updated_at": "2025-09-22T10:30:00.000000"
      }
    ],
    "total": 1,
    "skip": 0,
    "limit": 100
  },
  "metadata": {
    "statusCode": 200,
    "errors": [],
    "executionTime": 0.234,
    "timestamp": "2025-09-22T10:30:00.000000"
  },
  "success": 1
}
```

---

### 8. Get User by ID
**GET** `/auth/users/{user_id}`

Retrieve specific user by ID. Requires admin or super_admin role.

**Headers:**
```
Authorization: Bearer <admin-jwt-token>
```

**Path Parameters:**
- `user_id` (integer, required): User ID

**Response:**
```json
{
  "data": {
    "id": 1,
    "username": "john.doe.20250922103000123456",
    "email": "john.doe@example.com",
    "full_name": "John Doe",
    "role": "user",
    "is_active": true,
    "is_email_verified": true,
    "created_at": "2025-09-22T10:30:00.000000",
    "updated_at": "2025-09-22T10:30:00.000000"
  },
  "metadata": {
    "statusCode": 200,
    "errors": [],
    "executionTime": 0.123,
    "timestamp": "2025-09-22T10:30:00.000000"
  },
  "success": 1
}
```

---

## Diagnosis Endpoints

### 9. Generate Diagnosis
**POST** `/diagnosis/diagnose`

Generate AI-powered medical diagnosis based on patient symptoms and history.

**Headers:**
```
Authorization: Bearer <user-jwt-token>
```

**Request Body:**
```json
{
  "query": "Patient complains of chest pain and shortness of breath",
  "chat_history": [
    {
      "role": "user",
      "content": "Previous message"
    },
    {
      "role": "assistant", 
      "content": "Previous response"
    }
  ],
  "patient_data": {
    "age": 45,
    "gender": "male",
    "medical_history": ["hypertension", "diabetes"],
    "current_medications": ["metformin", "lisinopril"],
    "vital_signs": {
      "blood_pressure": "140/90",
      "heart_rate": 95,
      "temperature": 98.6
    }
  }
}
```

**Response:**
```json
{
  "data": {
    "diagnosis": {
      "primary_diagnosis": "Acute coronary syndrome",
      "differential_diagnoses": [
        "Myocardial infarction",
        "Unstable angina",
        "Pericarditis"
      ],
      "recommendations": [
        "Immediate ECG",
        "Cardiac enzymes",
        "Chest X-ray",
        "Consider cardiac catheterization"
      ],
      "urgency_level": "high",
      "confidence_score": 0.85
    },
    "query_classification": "cardiology",
    "context_used": "Retrieved relevant medical literature",
    "response_validation": "passed"
  },
  "metadata": {
    "statusCode": 200,
    "errors": [],
    "executionTime": 2.456,
    "timestamp": "2025-09-22T10:30:00.000000"
  },
  "success": 1
}
```

**Error Cases:**
- `401`: Unauthorized (invalid/missing token)
- `400`: Invalid input data
- `503`: AI service unavailable

---

### 10. Diagnosis Health Check
**GET** `/diagnosis/health`

Check the status of the AI diagnosis service.

**Response:**
```json
{
  "data": {
    "ai_service_status": "operational",
    "model_name": "gemini-2.5-flash",
    "vectorstore_status": "connected",
    "last_health_check": "2025-09-22T10:30:00.000000"
  },
  "metadata": {
    "statusCode": 200,
    "errors": [],
    "executionTime": 0.123,
    "timestamp": "2025-09-22T10:30:00.000000"
  },
  "success": 1
}
```

---

## System Endpoints

### 11. Application Health Check
**GET** `/health`

Check overall application health and service status.

**Response:**
```json
{
  "data": {
    "status": "healthy",
    "version": "2.0.0",
    "services": {
      "database": "connected",
      "ai_service": "operational",
      "email_service": "configured"
    },
    "timestamp": "2025-09-22T10:30:00.000000"
  },
  "metadata": {
    "statusCode": 200,
    "errors": [],
    "executionTime": 0.234,
    "timestamp": "2025-09-22T10:30:00.000000"
  },
  "success": 1
}
```

---

## User Roles

### Role Hierarchy:
1. **user**: Basic access to diagnosis features
2. **admin**: User management capabilities
3. **super_admin**: Full system access

### Role Permissions:
- **user**: Can access diagnosis endpoints
- **admin**: Can manage users (view, update user information)
- **super_admin**: Full administrative access

---

## Error Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

---

## Rate Limiting

Currently no rate limiting is implemented. Consider implementing rate limiting for production use.

---

## Security Features

1. **JWT Authentication**: Secure token-based authentication
2. **Password Hashing**: Bcrypt password hashing
3. **Email Verification**: Required before account activation
4. **Role-Based Access Control**: Granular permissions
5. **Input Validation**: Comprehensive request validation
6. **Error Sanitization**: Prevents information leakage
7. **PHI Encryption**: Patient data encryption support

---

## Environment Configuration

### Required Environment Variables:
```bash
# Database
DB_HOST=db
DB_PORT=5432
DB_NAME=healthnavi_cdss
DB_USER=healthnavi_user
DB_PASSWORD=SecurePass123!

# Security
SECRET_KEY=your-secret-key
ENCRYPTION_KEY=your-encryption-key

# Google Cloud AI
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# Email Service (Optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

---

## Testing

### Test User Registration Flow:
1. Register user: `POST /auth/register`
2. Verify email: `GET /auth/verify-email?token=<token>`
3. Login: `POST /auth/login`
4. Use diagnosis: `POST /diagnosis/diagnose`

### Test Admin Flow:
1. Register admin user
2. Login as admin
3. View users: `GET /auth/users`
4. Manage specific user: `GET /auth/users/{id}`

---

## Support

For technical support or questions about the API, please contact the development team.

**Last Updated:** September 22, 2025
**API Version:** 2.0.0
