import os
from dotenv import load_dotenv

load_dotenv()

# 📁 Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 🗄️ Database
DATABASE_PATH = os.path.join(BASE_DIR, "data", "database.db")

# 🔐 Security
SECRET_KEY = "restaurant_saas_v5_secret_key"

# 🤖 OpenAI (LLM)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

# 🏢 Default tenant
DEFAULT_TENANT_NAME = "Demo Restaurant"
DEFAULT_TENANT_CAPACITY = 20

# 👤 Default admin
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_ADMIN_ROLE = "super_admin"

# 🕒 Default working hours
DEFAULT_OPEN_HOUR = 10
DEFAULT_CLOSE_HOUR = 22