import os
import logging
import sys
import io
from datetime import datetime, timezone
import pytz
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automation.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Windows console encoding fix
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Status constants
STATUS_PENDING = "Pending"
STATUS_READY = "Ready" 
STATUS_COMPLETED = "Completed"
STATUS_FAILED = "Failed"

class Config:
    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Instagram API Configuration
    INSTAGRAM_API_VERSION = os.getenv("INSTAGRAM_API_VERSION", "v22.0")
    INSTAGRAM_BASE_URL = f"https://graph.instagram.com/{INSTAGRAM_API_VERSION}"
    INSTAGRAM_ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
    INSTAGRAM_BUSINESS_ID = os.getenv("INSTAGRAM_BUSINESS_ID")
    
    # Cloudinary Configuration
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

    # Airtable Configuration
    AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
    AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
    
    # Airtable Table Names
    AIRTABLE_POSTS_TABLE = os.getenv("AIRTABLE_POSTS_TABLE", "Posts")
    AIRTABLE_RETRY_TABLE = os.getenv("AIRTABLE_RETRY_TABLE", "Retry Queue")
    AIRTABLE_ACCOUNT_INSIGHTS_TABLE = os.getenv("AIRTABLE_ACCOUNT_INSIGHTS_TABLE", "Account Insights")
    AIRTABLE_MEDIA_INSIGHTS_TABLE = os.getenv("AIRTABLE_MEDIA_INSIGHTS_TABLE", "Media Insights")
    
    # Field name constants - update these to match your Airtable exactly
    FIELD_PROMPT = os.getenv("AIRTABLE_FIELD_PROMPT", "Prompt")
    FIELD_CAPTION = os.getenv("AIRTABLE_FIELD_CAPTION", "Generated Captions")
    FIELD_IMAGE_URL = os.getenv("AIRTABLE_FIELD_IMAGE_URL", "Image URL")
    FIELD_PUBLISHED = os.getenv("AIRTABLE_FIELD_PUBLISHED", "Published")
    FIELD_MEDIA_ID = os.getenv("AIRTABLE_FIELD_MEDIA_ID", "Media ID")
    FIELD_PUBLISH_DATE = os.getenv("AIRTABLE_FIELD_PUBLISH_DATE", "Publish Date")
    FIELD_STATUS = os.getenv("AIRTABLE_FIELD_STATUS", "Status")
    
    # Analytics table field name constants
    FIELD_TIMESTAMP = "Timestamp"
    FIELD_ACCOUNTS_ENGAGED = "Accounts Engaged"
    FIELD_REACH = "Reach"
    FIELD_PROFILE_VIEWS = "Profile Views"
    FIELD_VIEWS = "Views"
    FIELD_TOTAL_INTERACTIONS = "Total Interactions"
    FIELD_MEDIA_PRODUCT_TYPE = "Media Product Type"
    FIELD_LIKES = "Likes"
    FIELD_COMMENTS = "Comments"
    FIELD_SHARES = "Shares"
    FIELD_SAVED = "Saved"
    
    # Analytics Configuration
    ACCOUNT_INSIGHT_CONFIGS = {
        'account_engagement': {
            'name': 'Account Engagement',
            'metric': 'accounts_engaged',
            'metric_type': 'total_value'
        },
        'reach_breakdown': {
            'name': 'Reach Breakdown',
            'metric': 'reach',
            'breakdown': 'follow_type,media_product_type',
            'metric_type': 'total_value'
        },
        'profile_activity': {
            'name': 'Profile Activity',
            'metric': 'profile_views',
            'metric_type': 'total_value'
        },
        'views_breakdown': {
            'name': 'Views Breakdown',
            'metric': 'views',
            'breakdown': 'follow_type',
            'metric_type': 'total_value'
        },
        'content_interaction': {
            'name': 'Content Interaction',
            'metric': 'total_interactions',
            'breakdown': 'media_product_type',
            'metric_type': 'total_value'
        }
    }
    
    # Media Type Metrics Mapping
    MEDIA_METRICS = {
        'IMAGE': 'likes,comments,shares,saved,reach',
        'VIDEO': 'plays,likes,comments,shares,saved,reach',
        'CAROUSEL_ALBUM': 'likes,comments,shares,saved,reach,carousel_album_engagement',
        'STORY': 'impressions,reach,exits,replies',
        'DEFAULT': 'likes,comments,shares,saved,reach'
    }
    
    # Raw insights directory for JSON data
    RAW_INSIGHTS_DIR = "raw_insights"
    
    # Company name for caption generation
    COMPANY_NAME = os.getenv("COMPANY_NAME", "The Tech Boss")
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Karachi")
    
    # Image save path
    IMAGE_SAVE_PATH = os.getenv("IMAGE_SAVE_PATH", "Generated Images")
    
    @property
    def local_now(self):
        """Get current datetime in configured timezone"""
        try:
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo(self.TIMEZONE))
        except (ImportError, ModuleNotFoundError):
            return datetime.now(pytz.timezone(self.TIMEZONE))

# Create a global instance of the config
config = Config()