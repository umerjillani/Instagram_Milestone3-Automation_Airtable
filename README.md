# Instagram Automation System

A comprehensive automation system for Instagram content creation and publishing, now powered by Airtable for data management.

## System Overview

This system automates Instagram content creation and publishing using:
- **AI Content Generation**: GPT-4 for captions, DALL-E 3 for images
- **Cloud Storage**: Cloudinary for image hosting
- **Instagram Integration**: Graph API for direct publishing
- **Data Management**: Airtable for content and queue management
- **Workflow Management**: Automated scheduling via Python

## Prerequisites

### A. Software Requirements

| Tool | Download Link | Version |
|------|--------------|---------|
| Python | [python.org](https://www.python.org) | 3.9+ |
| VS Code | [code.visualstudio.com](https://code.visualstudio.com) | Latest |
| Git | [git-scm.com](https://git-scm.com) | 2.30+ |

### B. Required Accounts

1. **OpenAI Account**
   - Sign up at [platform.openai.com](https://platform.openai.com)
   - Required for API key

2. **Cloudinary Account**
   - Sign up at [cloudinary.com](https://cloudinary.com)
   - Required for image hosting

3. **Instagram Business Account**
   - Convert personal account to business account
   - Required for Graph API access

4. **Airtable Account**
   - Sign up at [airtable.com](https://airtable.com)
   - Required for content management

## Installation & Setup

### Step 1: Clone Repository

```bash
git clone <repository_link>
cd <project_directory>
```

### Step 2: Create and Activate Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

## Configuration

### Step 4: Set Up Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# OpenAI
OPENAI_API_KEY="your-openai-api-key"

# Cloudinary
CLOUDINARY_CLOUD_NAME="your-cloud-name"
CLOUDINARY_API_KEY="your-api-key"
CLOUDINARY_API_SECRET="your-api-secret"

# Instagram
INSTAGRAM_BUSINESS_ID="your-business-id"
ACCESS_TOKEN="your-access-token"
INSTAGRAM_API_VERSION="v22.0"

# Airtable
AIRTABLE_API_KEY="your-airtable-api-key"
AIRTABLE_BASE_ID="your-base-id"
AIRTABLE_POSTS_TABLE="Posts"
AIRTABLE_RETRY_TABLE="Retry Queue"
AIRTABLE_ACCOUNT_INSIGHTS_TABLE="Account Insights"
AIRTABLE_MEDIA_INSIGHTS_TABLE="Media Insights"

# Optional Configuration
COMPANY_NAME="Your Company Name"
TIMEZONE="Your Timezone"
IMAGE_SAVE_PATH="Generated Images"
```

### Step 5: Airtable Setup

#### A. Generate Airtable API Key
1. Log in to your Airtable account
2. Go to [Airtable API Documentation](https://airtable.com/developers/web/api/introduction)
3. Click on "Generate API key"
4. Copy the generated API key to your `.env` file

#### B. Create Airtable Base
1. Create a new base in Airtable
2. Copy the Base ID from the URL (e.g., `https://airtable.com/appXXXXXXXXXXXXXX` → `appXXXXXXXXXXXXXX`)
3. Add the Base ID to your `.env` file

#### C. Table Structure Setup

1. **Posts Table** (`Posts`)
   | Field Name | Field Type | Description |
   |------------|------------|-------------|
   | Prompt | Single line text | Content generation prompt |
   | Generated Captions | Long text | Generated Instagram caption |
   | Image URL | URL | Cloudinary image URL |
   | Published | Single select | Options: Yes, No |
   | Media ID | Single line text | Instagram post ID |
   | Publish Date | Date & Time | Scheduled publish date |
   | Status | Single select | Options: Pending, Ready, Completed, Failed |

2. **Retry Queue Table** (`Retry Queue`)
   | Field Name | Field Type | Description |
   |------------|------------|-------------|
   | Operation | Single line text | Type of operation to retry |
   | Record ID | Single line text | ID of the record to retry |
   | Details | Long text | Operation details |
   | Status | Single select | Options: Pending, Completed, Failed |
   | Created | Date & Time | Timestamp of creation |

3. **Account Insights Table** (`Account Insights`)
   | Field Name | Field Type | Description |
   |------------|------------|-------------|
   | Timestamp | Date & Time | Analytics timestamp |
   | Accounts Engaged | Number | Number of accounts engaged |
   | Reach | Number | Total reach |
   | Profile Views | Number | Number of profile views |
   | Views | Number | Total views |
   | Total Interactions | Number | Total interactions |

4. **Media Insights Table** (`Media Insights`)
   | Field Name | Field Type | Description |
   |------------|------------|-------------|
   | Timestamp | Date & Time | Analytics timestamp |
   | Media ID | Single line text | Instagram media ID |
   | Media Product Type | Single select | Options: FEED, STORY, REELS |
   | Likes | Number | Number of likes |
   | Comments | Number | Number of comments |
   | Shares | Number | Number of shares |
   | Saved | Number | Number of saves |
   | Reach | Number | Total reach |

### Step 6: Instagram Business ID & Access Token

1. Use the `GetIGBusiness_Id.ipynb` notebook to obtain your Instagram Business ID:
   - Open the notebook
   - Replace `PASTE_YOUR_TOKEN_HERE` with your Instagram access token
   - Run the notebook
   - Copy the Business ID to your `.env` file

2. Generate Instagram Access Token:
   - Go to your Meta Developer App
   - Navigate to Instagram API Setup
   - Add your Instagram Business Account
   - Generate Access Token
   - Copy the token to your `.env` file

## Running the System

### Content Automation

```bash
python airtable_content_automation.py
```

This script:
- Generates content using AI
- Stores content in Airtable
- Manages the publishing queue
- Handles retries for failed posts

### Analytics Collection

```bash
python instagram_analytics.py
```

This script:
- Collects Instagram insights
- Updates analytics in Airtable
- Generates reports

## Logging

The system maintains two log files:
- `automation.log`: Records content generation and posting activities
- `analytics.log`: Records analytics collection activities

## Troubleshooting

1. **Airtable Connection Issues**
   - Verify API key and base ID in `.env`
   - Check internet connection
   - Verify table names match exactly
   - Ensure field types match the specified types
   - Check table relationships are properly set up

2. **Instagram Posting Issues**
   - Verify access token is valid
   - Check Instagram Business ID
   - Ensure account has necessary permissions

3. **AI Generation Issues**
   - Verify OpenAI API key
   - Check API rate limits
   - Verify prompt templates

