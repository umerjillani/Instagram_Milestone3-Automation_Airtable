# from pyairtable import Api

# API_KEY = "pat1FZ85cJpjLy59H.3366c3e073b653a28a3d01c2f5fe73cf20c9d42cb1d0cfb8c3d2be376d296338"
# BASE_ID = "app2KIcT14sEdX9YK"
# TABLE_NAME = "Posts"  # or whatever your table is named

from pyairtable import Api, Table
import os

from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("AIRTABLE_API_KEY")
base_id = os.getenv("AIRTABLE_BASE_ID")

# Try to access both tables
try:
    posts_table = Table(api_key, base_id, "Posts")
    posts = posts_table.all(max_records=1)
    print(f"Posts table accessible! Found {len(posts)} records")
except Exception as e:
    print(f"Error accessing Posts table: {e}")

try:
    retry_table = Table(api_key, base_id, "Retry Queue")
    retries = retry_table.all(max_records=1)
    print(f"Retry Queue table accessible! Found {len(retries)} records")
except Exception as e:
    print(f"Error accessing Retry Queue table: {e}")