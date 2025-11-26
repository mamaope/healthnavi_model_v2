# Google OAuth Setup Guide

## Step 1: Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select or create a project
3. Navigate to **APIs & Services** > **Credentials**
4. Click **Create Credentials** > **OAuth client ID**
5. If prompted, configure the OAuth consent screen first:
   - Choose **External** (unless you have a Google Workspace)
   - Fill in the required fields (App name, User support email, Developer contact)
   - Add scopes: `openid`, `email`, `profile`
   - Add test users (for development)
6. Create OAuth client ID:
   - Application type: **Web application**
   - Name: **HealthNavi OAuth Client**
   - Authorized redirect URIs:
     - `http://localhost:8050/api/v2/auth/google/callback` (for local development)
     - `https://yourdomain.com/api/v2/auth/google/callback` (for production)
7. Copy the **Client ID** and **Client Secret**

## Step 2: Add Environment Variables

Add these variables to your `.env` file in the project root:

```env
# Google OAuth Configuration
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8050/api/v2/auth/google/callback

# Backend and Frontend URLs (for OAuth redirects)
BACKEND_URL=http://localhost:8050
FRONTEND_URL=http://localhost:5173
```

## Step 3: Update Docker Compose (if using Docker)

If you're using Docker, you can add these to your `docker-compose.yml` under the `api` service:

```yaml
environment:
  - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
  - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
  - GOOGLE_REDIRECT_URI=${GOOGLE_REDIRECT_URI}
  - BACKEND_URL=${BACKEND_URL}
  - FRONTEND_URL=${FRONTEND_URL}
```

Or they will be automatically loaded from the `.env` file if you're using `env_file: - .env`.

## Step 4: Restart Your Application

After adding the environment variables:

```bash
# If using Docker
docker-compose restart api

# If running locally
# Restart your backend server
```

## Important Notes

- **Development**: Use `http://localhost:8050` for local development
- **Production**: Update the redirect URI to your production domain
- **Security**: Never commit your `.env` file or OAuth credentials to version control
- **HTTPS**: In production, use HTTPS URLs for redirect URIs

## Testing

1. Click "Continue with Google" button in the login modal
2. You should be redirected to Google's login page
3. After authentication, you'll be redirected back and logged in

