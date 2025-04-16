import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
from pyairtable import Api, Base, Table
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

from config import config, logging, STATUS_PENDING, STATUS_READY, STATUS_COMPLETED, STATUS_FAILED

# Airtable client class for better error handling
class AirtableAnalyticsClient:
    def __init__(self, api_key, base_id):
        self.api = Api(api_key)
        self.base = Base(self.api, base_id)
        self.account_table = self.base.table(config.AIRTABLE_ACCOUNT_INSIGHTS_TABLE)
        self.media_table = self.base.table(config.AIRTABLE_MEDIA_INSIGHTS_TABLE)
        self.posts_table = self.base.table(config.AIRTABLE_POSTS_TABLE)  # For fetching Media IDs
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def safe_request(self, fn, *args, **kwargs):
        """Execute Airtable requests with retry logic for rate limits"""
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logging.error(f"Airtable request failed: {e}")
            if "RATE_LIMIT" in str(e):
                logging.warning("Rate limited by Airtable, retrying...")
                raise  # This will trigger retry
            raise
            
    def validate_tables(self):
        """Validate that the required tables exist"""
        try:
            # Try getting a record from each table
            self.safe_request(self.account_table.first)
            self.safe_request(self.media_table.first)
            self.safe_request(self.posts_table.first)
            logging.info("All required tables exist in Airtable")
            return True
        except Exception as e:
            logging.error(f"Error validating tables: {e}")
            return False
            
    def get_media_ids(self):
        """Get media IDs from Airtable Posts table"""
        try:
            records = self.safe_request(
                self.posts_table.all,
                formula=f"AND({{{config.FIELD_PUBLISHED}}} = 'Yes', {{{config.FIELD_MEDIA_ID}}} != '')"
            )
            
            media_ids = []
            for record in records:
                media_id = record['fields'].get(config.FIELD_MEDIA_ID)  # Updated to Title Case
                if media_id:
                    media_ids.append(media_id)
                    
            logging.info(f"Found {len(media_ids)} posts with Media IDs")
            return media_ids
        except Exception as e:
            logging.error(f"Error getting media IDs: {e}")
            return []
            
    def create_account_insight(self, data):
        """Create or update an account insight record in Airtable with Title Case columns"""
        try:
            # Format timestamp
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Initialize with fields using Title Case
            record = {
                config.FIELD_TIMESTAMP: timestamp,
                config.FIELD_ACCOUNTS_ENGAGED: 0,
                config.FIELD_REACH: 0,
                config.FIELD_PROFILE_VIEWS: 0,
                config.FIELD_VIEWS: 0,
                config.FIELD_TOTAL_INTERACTIONS: 0
            }
            
            # Extract metrics and map to your Title Case fields
            for insight_key, insight_data in data.items():
                for metric in insight_data.get('data', []):
                    metric_name = metric.get('name')
                    total_value = metric.get('total_value', {}).get('value') or \
                                sum(v.get('value', 0) for v in metric.get('values', []))
                    
                    # Map Instagram metrics to Title Case fields
                    if metric_name == 'accounts_engaged':
                        record[config.FIELD_ACCOUNTS_ENGAGED] = total_value
                    elif metric_name == 'reach':
                        record[config.FIELD_REACH] = total_value
                    elif metric_name == 'profile_views':
                        record[config.FIELD_PROFILE_VIEWS] = total_value
                    elif metric_name == 'views':
                        record[config.FIELD_VIEWS] = total_value
                    elif metric_name == 'total_interactions':
                        record[config.FIELD_TOTAL_INTERACTIONS] = total_value            
            
            # Check if record already exists - get the most recent one
            # First check for any existing records (up to the most recent 100)
            existing_records = self.safe_request(
                self.account_table.all,
                sort=["-" + config.FIELD_TIMESTAMP]  # Sort by timestamp in descending order
            )
            
            if existing_records:
                # Update the most recent record
                most_recent = existing_records[0]
                updated = self.safe_request(self.account_table.update, most_recent['id'], record)
                logging.info(f"Updated account insight record with ID: {most_recent.get('id')}")
                return updated
            else:
                # Create new record if none exists
                created = self.safe_request(self.account_table.create, record)
                logging.info(f"Created account insight record with ID: {created.get('id')}")
                return created
        except Exception as e:
            logging.error(f"Error creating/updating account insight: {e}")
            return None
                    
    def create_media_insight(self, media_data):
        """Create media insight records in Airtable with Title Case columns"""
        try:
            created_records = []
            for item in media_data:
                if not item or 'insights' not in item:
                    continue
                
                # Format timestamp
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Initialize with fields using Title Case
                record = {
                    config.FIELD_TIMESTAMP: timestamp,
                    config.FIELD_MEDIA_ID: item['media_id'],
                    config.FIELD_MEDIA_PRODUCT_TYPE: item.get('media_product_type', 'FEED'),
                    config.FIELD_LIKES: 0,
                    config.FIELD_COMMENTS: 0,
                    config.FIELD_SHARES: 0,
                    config.FIELD_SAVED: 0,
                    config.FIELD_REACH: 0
                }
                
                # Extract metrics
                for metric in item['insights'].get('data', []):
                    metric_name = metric.get('name')
                    value = metric.get('values', [{}])[0].get('value', 0)
                    
                    # Map Instagram metrics to Title Case fields
                    if metric_name == 'likes':
                        record[config.FIELD_LIKES] = value
                    elif metric_name == 'comments':
                        record[config.FIELD_COMMENTS] = value
                    elif metric_name == 'shares':
                        record[config.FIELD_SHARES] = value
                    elif metric_name == 'saved':
                        record[config.FIELD_SAVED] = value
                    elif metric_name == 'reach':
                        record[config.FIELD_REACH] = value        
                                
                # Check if record already exists - update formula to use Title Case
                existing = self.safe_request(
                    self.media_table.first,
                    formula=f"{{{config.FIELD_MEDIA_ID}}} = '{item['media_id']}'"
                )
                
                if existing:
                    # Update existing record
                    updated = self.safe_request(self.media_table.update, existing['id'], record)
                    logging.info(f"Updated media insight for {item['media_id']}")
                else:
                    # Create new record
                    created = self.safe_request(self.media_table.create, record)
                    created_records.append(created)
                    logging.info(f"Created media insight for {item['media_id']}")
            
            return created_records
        except Exception as e:
            logging.error(f"Error creating media insights: {e}")
            return None
        
def get_unix_timestamps(days=30):
    """Calculate timestamps for specified number of days"""
    yesterday = datetime.now() - timedelta(days=1)
    since_date = yesterday - timedelta(days=days)
    return {
        'since': int(since_date.timestamp()),
        'until': int(yesterday.replace(hour=23, minute=59, second=59).timestamp())
    }

def save_raw_data(data, filename):
    """Save raw JSON data to file with single account insights file"""
    os.makedirs(config.RAW_INSIGHTS_DIR, exist_ok=True)
    filepath = os.path.join(config.RAW_INSIGHTS_DIR, filename)
    with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def fetch_account_insights(days=30):
    """Fetch account-level insights with proper time range"""
    try:
        all_insights = {}
        logging.info("Starting Account Insights Collection...")
        for insight_key, insight_config in config.ACCOUNT_INSIGHT_CONFIGS.items():
            logging.info(f"Fetching {insight_config['name']}...")  
            effective_days = min(days, insight_config.get('max_days', days))  
            timestamps = get_unix_timestamps(effective_days)
            
            params = {
                'access_token': config.INSTAGRAM_ACCESS_TOKEN,
                'metric': insight_config['metric'],
                'period': 'day',
                'metric_type': insight_config['metric_type'],
                'since': timestamps['since'],
                'until': timestamps['until']
            }

            if 'breakdown' in insight_config:
                params['breakdown'] = insight_config['breakdown']

            try:
                response = requests.get(f"{config.INSTAGRAM_BASE_URL}/{config.INSTAGRAM_BUSINESS_ID}/insights", params=params)
                response.raise_for_status()
                result = response.json()
                all_insights[insight_key] = result
                logging.info(f"{insight_config['name']} collected")
                time.sleep(1)
                
            except Exception as e:
                logging.error(f"Error fetching {insight_config['name']}: {str(e)}")
        
        # Save all account insights in single file
        save_raw_data(all_insights, f"account_insights_{datetime.now().strftime('%Y%m%d')}.json")
        return all_insights

    except Exception as e:
        logging.error(f"Account insights error: {str(e)}")
        return None
        
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def fetch_media_insights(media_id):
    """Fetch insights for a single media item"""
    try:
        media_id = str(media_id).strip().lstrip("'")
        
        if not media_id.isdigit():
            raise ValueError(f"Invalid Media ID format: {media_id}")
        
        # Get media type from Instagram API
        media_info = requests.get(
            f"{config.INSTAGRAM_BASE_URL}/{media_id}",
            params={'access_token': config.INSTAGRAM_ACCESS_TOKEN, 'fields': 'media_product_type,caption,timestamp'}
        ).json()
        
        # Get media product type correctly
        media_product_type = media_info.get('media_product_type', 'FEED')
        caption = media_info.get('caption', '')[:100]
        post_date = media_info.get('timestamp', '')
        
        if post_date:
            # Convert Instagram datetime to Excel format
            try:
                dt = datetime.fromisoformat(post_date.replace('Z', '+00:00'))
                post_date = dt.strftime('%m/%d/%Y %H:%M:%S')
            except:
                post_date = datetime.now().strftime('%m/%d/%Y %H:%M:%S')
        
        # Get appropriate metrics
        metrics = config.MEDIA_METRICS.get(media_product_type, config.MEDIA_METRICS['DEFAULT'])

        params = {
            'access_token': config.INSTAGRAM_ACCESS_TOKEN,
            'metric': metrics
        }

        response = requests.get(f"{config.INSTAGRAM_BASE_URL}/{media_id}/insights", params=params)
        response.raise_for_status()
        
        # Save raw media insights
        save_raw_data(response.json(), f"media_{media_id}_{datetime.now().strftime('%Y%m%d')}.json")
        
        return {
            'media_id': media_id,
            'media_product_type': media_product_type,
            'caption': caption,
            'post_date': post_date,
            'insights': response.json(),
            'timestamp': datetime.now().strftime('%m/%d/%Y %H:%M:%S')
        }

    except Exception as e:
        logging.error(f"Error fetching insights for {media_id}: {str(e)}")
        return None

def collect_analytics(days=30):
    """Main function to collect analytics data and store in Airtable"""
    logging.info("Instagram Insights Collector (Airtable Version)")
    logging.info("------------------------------")
    
    try:
        # Initialize Airtable client
        airtable_client = AirtableAnalyticsClient(config.AIRTABLE_API_KEY, config.AIRTABLE_BASE_ID)        
        # Validate tables
        if not airtable_client.validate_tables():
            logging.error("Table validation failed. Please check your Airtable setup.")
            return False
        
        # Fetch account insights
        account_data = fetch_account_insights(days)
        if account_data:
            airtable_client.create_account_insight(account_data)
            logging.info("Account insights saved to Airtable")
        
        # Fetch media insights
        media_ids = airtable_client.get_media_ids()
        if media_ids:
            media_data = []
            logging.info("\nCollecting Media Insights...")
            for idx, media_id in enumerate(media_ids, 1):
                logging.info(f"Processing media {idx}/{len(media_ids)} - ID: {media_id}")
                insights = fetch_media_insights(media_id)
                if insights:
                    media_data.append(insights)
                time.sleep(1)
            
            if media_data:
                airtable_client.create_media_insight(media_data)
                logging.info(f"Media insights saved for {len(media_data)} posts")
        
        logging.info("\nData collection completed!")
        return True
        
    except Exception as e:
        logging.error(f"Error in analytics collection: {str(e)}")
        return False

# Run the collector if script is executed directly
if __name__ == "__main__":
    collect_analytics(days=30)