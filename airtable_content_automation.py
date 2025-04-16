import time
import requests
import logging
import os
import re
from openai import OpenAI
import schedule
from datetime import datetime, timezone
import pytz
from pyairtable import Api, Base, Table
from cloudinary_utils import upload_image
from instagram_poster import publish_single_post
from tenacity import retry, stop_after_attempt, wait_exponential
from config import config, logging, STATUS_PENDING, STATUS_READY, STATUS_COMPLETED, STATUS_FAILED
import sys
import io


os.makedirs(config.IMAGE_SAVE_PATH, exist_ok=True)

# AirtableClient class for centralized Airtable operations
class AirtableClient:
    def __init__(self, api_key, base_id):
        self.api = Api(api_key)
        self.base = Base(self.api, base_id)
        self.posts_table = self.base.table(config.AIRTABLE_POSTS_TABLE)
        self.retry_table = self.base.table(config.AIRTABLE_RETRY_TABLE)
        
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
    
    def get_records_needing_captions(self):
        """Get records that need captions generated"""
        return self.safe_request(
            self.posts_table.all,
            formula=f"AND({{{config.FIELD_CAPTION}}} = '', {{{config.FIELD_PUBLISHED}}} != 'Yes')"
        )
    
    def get_records_needing_images(self):
        """Get records that need images generated"""
        return self.safe_request(
            self.posts_table.all,
            formula=f"AND({{{config.FIELD_CAPTION}}} != '', {{{config.FIELD_IMAGE_URL}}} = '', {{{config.FIELD_PUBLISHED}}} != 'Yes')"
        )
    
    def get_unpublished_ready_posts(self):
        """Get posts that are ready to be published"""
        return self.safe_request(
            self.posts_table.all,
            formula=f"AND({{{config.FIELD_IMAGE_URL}}} != '', {{{config.FIELD_PUBLISHED}}} != 'Yes', {{{config.FIELD_STATUS}}} = '{STATUS_READY}')"
        )
    
    def get_any_unpublished_posts(self):
        """Get any unpublished posts with images"""
        return self.safe_request(
            self.posts_table.all,
            formula=f"AND({{{config.FIELD_IMAGE_URL}}} != '', {{{config.FIELD_PUBLISHED}}} != 'Yes')"
        )
    
    def update_record(self, record_id, fields):
        """Update a single record with error handling"""
        try:
            self.safe_request(
                self.posts_table.update,
                record_id, 
                fields
            )
            self.log_operation("update", record_id, True)
            return True
        except Exception as e:
            self.log_operation("update", record_id, False, str(e))
            self.add_to_retry_queue("update", record_id, fields)
            return False
    
    def batch_update_records(self, records_data):
        """Update multiple records in a single API call"""
        if not records_data:
            return True
            
        try:
            batch_operations = [{"id": record_id, "fields": fields} for record_id, fields in records_data]
            self.safe_request(
                self.posts_table.batch_update,
                batch_operations
            )
            for record_id, _ in records_data:
                self.log_operation("batch_update", record_id, True)
            return True
        except Exception as e:
            logging.error(f"Batch update failed: {e}")
            # If batch fails, add individual records to retry queue
            for record_id, fields in records_data:
                self.log_operation("batch_update", record_id, False, str(e))
                self.add_to_retry_queue("update", record_id, fields)
            return False
    
    def add_to_retry_queue(self, operation, record_id, details=None):
        """Add failed operation to retry queue"""
        try:
            self.safe_request(
                self.retry_table.create,
                {
                    "Operation": operation,
                    "Record ID": record_id,
                    "Details": str(details) if details else None,
                    "Status": STATUS_PENDING,
                    "Created": datetime.now(timezone.utc).isoformat()
                }
            )
            logging.info(f"Added {operation} for record {record_id} to retry queue")
            return True
        except Exception as e:
            logging.error(f"Failed to add to retry queue: {e}")
            return False
    
    def process_retry_queue(self):
        """Process pending items in retry queue"""
        try:
            # First check if we can access the table at all
            test = self.retry_table.first()
            if test is None:
                logging.info("Retry Queue table exists but is empty")
            
            retry_items = self.safe_request(
                self.retry_table.all,
                formula=f"{{Status}} = '{STATUS_PENDING}'"
            )
            
            for item in retry_items:
                item_id = item['id']
                fields = item['fields']
                operation = fields.get('Operation')
                record_id = fields.get('Record ID')
                details = fields.get('Details')
                
                success = False
                
                # Process based on operation type
                if operation == "update":
                    try:
                        # Try to parse details back into a dict
                        import ast
                        update_fields = ast.literal_eval(details) if details else {}
                        success = self.update_record(record_id, update_fields)
                    except Exception as e:
                        logging.error(f"Failed to retry update: {e}")
                
                # Update retry queue item
                status = STATUS_COMPLETED if success else STATUS_FAILED
                self.safe_request(
                    self.retry_table.update,
                    item_id, 
                    {"Status": status}
                )
        except Exception as e:
            logging.warning(f"Could not process retry queue: {e}")
            
    def log_operation(self, operation, record_id, success, details=None):
        """Log Airtable operations with consistent format"""
        status = "✅" if success else "❌"
        msg = f"{status} Airtable {operation} - Record: {record_id}"
        if details:
            msg += f" - Details: {details}"
        
        if success:
            logging.info(msg)
        else:
            logging.error(msg)
    
    def validate_table_structure(self):
        """Validate that all required fields exist in Airtable table"""
        try:
            # Note: This is using an unofficial method and might break in future pyairtable versions
            try:
                table_info = self.posts_table._table_info()
                fields = [field['name'] for field in table_info['fields']]
            except:
                # Fallback - get a record and check its keys
                records = self.posts_table.all(max_records=1)
                if not records:
                    logging.warning("Could not validate table structure - no records found")
                    return True  # Assume it's OK if empty
                
                # Get all possible fields from the API
                fields = list(records[0]['fields'].keys())
            
            # Check all required fields exist
            required_fields = [
                config.FIELD_PROMPT, 
                config.FIELD_CAPTION, 
                config.FIELD_IMAGE_URL,
                config.FIELD_PUBLISHED, 
                config.FIELD_MEDIA_ID, 
                config.FIELD_PUBLISH_DATE, 
                config.FIELD_STATUS
            ]
            
            missing_fields = [field for field in required_fields if field not in fields]
            
            if missing_fields:
                logging.error(f"Missing required fields in Airtable: {missing_fields}")
                return False
            
            return True
        except Exception as e:
            logging.error(f"Failed to validate Airtable structure: {e}")
            return False


# Initialize Airtable client
airtable_client = AirtableClient(config.AIRTABLE_API_KEY, config.AIRTABLE_BASE_ID)

# Function to sanitize file names
def sanitize_filename(filename):
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)  # Remove invalid characters
    filename = filename.replace(' ', '_')  # Replace spaces with underscores
    filename = filename[:50]  # Limit the length of the filename
    return filename

class CaptionGenerator:
    def __init__(self, openai_api_key):
        self.openai_api_key = openai_api_key
        self.url = "https://api.openai.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate_caption(self, prompt):
        data = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Please generate a detailed caption and relevant hashtags, ensuring hashtags are included."}
            ]
        }

        try:
            response = requests.post(self.url, headers=self.headers, json=data)
            response.raise_for_status()
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', "")
            
            if "Hashtags:" in content:
                caption, hashtags_str = content.split("Hashtags:", 1)
                caption = caption.strip().replace("\n", " ").replace('"', '')  # Remove quotes
                hashtags_list = [tag.strip() for tag in hashtags_str.strip().split() if tag.startswith("#")]
                hashtags = " ".join(hashtags_list)
                return {"caption": caption, "hashtags": hashtags}
            
            return {"caption": content.strip().replace("\n", " ").replace('"', ''), "hashtags": ""}
        
        except requests.exceptions.RequestException as err:
            logging.error(f"Request error: {err}")
            if "429" in str(err):  # Rate limit error
                logging.warning("Rate limit exceeded. Retrying...")
                raise  # This will trigger retry
            return {"error": str(err)}

    def generate_captions_from_airtable(self, company_name):
        try:
            # Get records where Generated Captions is empty
            records = airtable_client.get_records_needing_captions()
            
            # Add debug info
            logging.info(f"Found {len(records)} records needing captions")
            
            if not records:
                logging.info("No new prompts found. Skipping caption generation.")
                return {"status": "No new prompts found"}

            new_captions_generated = False
            batch_updates = []

            # Print record details for debugging
            for record in records:
                record_id = record['id']
                fields = record['fields']
                logging.info(f"Processing record {record_id} with fields: {fields}")
                
                if config.FIELD_PROMPT in fields and fields[config.FIELD_PROMPT]:
                    content = fields[config.FIELD_PROMPT]
                    prompt = f"Generate a detailed caption based on {content} and {company_name}, include power words and realism and include 10 relevant hashtags at the end of the caption."
                    result = self.generate_caption(prompt)
                    
                    if isinstance(result, dict) and "error" in result:
                        logging.error(f"Error for record {record_id}: {result['error']}")
                        batch_updates.append((record_id, {
                            config.FIELD_CAPTION: "API Error: Rate limit exceeded",
                            config.FIELD_STATUS: STATUS_FAILED
                        }))
                    else:
                        # Since you don't have separate hashtags field, include hashtags in caption
                        full_caption = f"{result['caption']} {result['hashtags']}"
                        batch_updates.append((record_id, {
                            config.FIELD_CAPTION: full_caption,
                            config.FIELD_STATUS: STATUS_PENDING
                        }))
                        new_captions_generated = True
                        logging.info(f"Caption generated for record {record_id}")

            # Update all records in a batch
            if batch_updates:
                airtable_client.batch_update_records(batch_updates)

            if new_captions_generated:
                logging.info("Captions generated successfully.")
            
            return {"status": "Caption generation completed"}
        
        except Exception as e:
            logging.error(f"Error generating captions from Airtable: {e}")
            return {"error": f"Failed to generate captions: {str(e)}"}
        
    
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def generate_image(prompt, save_path):
    try:
        # Placeholder for DALL-E image generation
        # Replace this with your actual DALL-E implementation
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="hd",
            n=1,
        )

        image_url = response.data[0].url
        image_data = requests.get(image_url).content
        
        # Sanitize the file name
        file_name = sanitize_filename(prompt[:50])  # Use the first 50 characters of the prompt
        file_path = f"{save_path}/{file_name}.png"
        
        with open(file_path, "wb") as file:
            file.write(image_data)
        logging.info(f"Image saved: {file_path}")
        return file_path
    except Exception as e:
        logging.error(f"Error generating image: {e}")
        if "429" in str(e):  # Rate limit error
            logging.warning("Rate limit exceeded. Retrying...")
            raise  # This will trigger retry
        return None

def generate_images_from_airtable(save_path):
    try:
        # Get records with captions but no image URL
        records = airtable_client.get_records_needing_images()
        
        if not records:
            logging.info("No new images to generate.")
            return {"status": "No new images to generate"}

        new_images_generated = False
        batch_updates = []
        
        for record in records:
            record_id = record['id']
            fields = record['fields']
            
            if config.FIELD_CAPTION in fields and fields[config.FIELD_CAPTION]:
                caption = fields[config.FIELD_CAPTION]
                prompt = caption  # Use caption as prompt for image generation
                
                logging.info(f"Processing prompt for record {record_id}: {prompt[:50]}...")
                
                # Generate image
                image_path = generate_image(prompt, save_path)
                if not image_path:
                    batch_updates.append((record_id, {config.FIELD_STATUS: STATUS_FAILED}))
                    continue
                
                # Upload to Cloudinary
                image_url = upload_image(image_path)
                if image_url:
                    batch_updates.append((record_id, {
                        config.FIELD_IMAGE_URL: image_url,
                        config.FIELD_STATUS: STATUS_READY
                    }))
                    logging.info(f"Image uploaded to Cloudinary for record {record_id}. URL: {image_url}")
                    new_images_generated = True
                else:
                    batch_updates.append((record_id, {config.FIELD_STATUS: STATUS_FAILED}))
        
        # Update all records in a batch
        if batch_updates:
            airtable_client.batch_update_records(batch_updates)
        
        if new_images_generated:
            logging.info("Images generated and uploaded successfully.")
        
        return {"status": "Image generation completed"}
    
    except Exception as e:
        logging.error(f"Error generating images from Airtable: {e}")
        return {"error": f"Failed to generate images: {str(e)}"}
        
def process_next_post():
    """
    Processes the FIRST unpublished post in Airtable.
    Returns True if a post was processed, False if none left.
    """
    try:
        logging.info("Starting post processing...")
        print("\n🔍 Checking for unpublished posts...")
        
        # Try to get posts that are explicitly ready
        records = airtable_client.get_unpublished_ready_posts()
        
        # If none are explicitly Ready, try any unpublished with image
        if not records:
            records = airtable_client.get_any_unpublished_posts()
            
        if not records:
            msg = "All posts already published or not ready. No action needed."
            logging.info(msg)
            print(msg)
            return False
        
        # Get the first unpublished post
        record = records[0]
        record_id = record['id']
        fields = record['fields']
        
        print(f"📮 Found unpublished post: {record_id}")

        # Validate required data
        validation_errors = []
        if config.FIELD_IMAGE_URL not in fields or not fields[config.FIELD_IMAGE_URL]:
            validation_errors.append("Image URL")
        if config.FIELD_CAPTION not in fields or not fields[config.FIELD_CAPTION]:
            validation_errors.append("Generated Captions")
            
        if validation_errors:
            error_msg = f"Missing data in record {record_id}: {', '.join(validation_errors)}"
            logging.error(error_msg)
            print(error_msg)
            airtable_client.update_record(record_id, {config.FIELD_STATUS: STATUS_FAILED})
            return False

        # Get caption (full caption with hashtags)
        full_caption = fields[config.FIELD_CAPTION].strip()
        
        # Publish via Instagram Graph API
        print("Attempting to publish post...")
        media_id = publish_single_post(fields[config.FIELD_IMAGE_URL], full_caption)
        
        if media_id:
            success_msg = f"Successfully published post! Media ID: {media_id}"
            logging.info(success_msg)
            print(success_msg)
            
            # Update Airtable record - using the format you specified for publish date
            success = airtable_client.update_record(record_id, {
                config.FIELD_PUBLISHED: "Yes",
                config.FIELD_MEDIA_ID: media_id,
                config.FIELD_PUBLISH_DATE: config.local_now.strftime('%m/%d/%Y %H:%M:%S'),
                config.FIELD_STATUS: STATUS_COMPLETED
            })
            
            if success:
                logging.info(f"Updated Airtable record {record_id}")
            return True
            
        logging.warning("Post publication failed")
        airtable_client.update_record(record_id, {config.FIELD_STATUS: STATUS_FAILED})
        return False

    except Exception as e:
        error_msg = f"Critical error in process_next_post: {str(e)}"
        logging.error(error_msg, exc_info=True)
        print(error_msg)
        return False
    
    
# Function to collect and store analytics data
def collect_and_store_analytics(days=30):
    """
    Collects Instagram analytics and stores in Airtable.
    Replaces the Excel-based analytics collection.
    """
    try:
        logging.info(f"Collecting Instagram analytics for past {days} days...")
        
        # Import the analytics collection function
        from instagram_analytics import collect_analytics
        
        # Run the analytics collection
        result = collect_analytics(days)
        
        if result:
            logging.info("Successfully collected and stored analytics data in Airtable")
        else:
            logging.error("Failed to collect analytics data")
        
        return result
    except Exception as e:
        logging.error(f"Error in analytics collection: {str(e)}")
        return False
    
# Main function to automate the process
def automate_content_generation():
    logging.info("Starting content generation process...")
    
    # First validate Airtable structure
    if not airtable_client.validate_table_structure():
        logging.error("Airtable validation failed. Please check your table structure.")
        return {"error": "Airtable validation failed"}
    
    # Step 1: Generate captions
    caption_generator = CaptionGenerator(config.OPENAI_API_KEY)
    caption_result = caption_generator.generate_captions_from_airtable(config.COMPANY_NAME)
    logging.info(caption_result)

    # Step 2: Generate images
    image_result = generate_images_from_airtable(config.IMAGE_SAVE_PATH)
    logging.info(image_result)
    
    # Step 3: Process any items in the retry queue
    airtable_client.process_retry_queue()
    
    logging.info("Content generation completed. Ready for publishing.")

# Schedule jobs
schedule.every(1).minutes.do(process_next_post)
schedule.every(3).minutes.do(lambda: collect_and_store_analytics(days=30))
schedule.every(10).minutes.do(automate_content_generation)
schedule.every(15).minutes.do(lambda: airtable_client.process_retry_queue())

# Run the script directly
if __name__ == "__main__":
    logging.info("Script started.")
    automate_content_generation()
    
    # Run the scheduler
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logging.error(f"Error in scheduled task: {str(e)}")
            time.sleep(60)