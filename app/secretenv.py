from google.cloud import secretmanager
import os
import logging
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration map for secrets
SECRET_MAP = {
    "AUTH0_ALGORITHMS": "AUTH0_ALGORITHMS",
    "AUTH0_API_AUDIENCE": "AUTH0_API_AUDIENCE",
    "API_KEY": "AUTH0_API_KEY",
    "AUTH0_DOMAIN": "AUTH0_DOMAIN",
    "AUTH0_ISSUER": "AUTH0_ISSUER",
    "API_BASE_URL": "API_BASE_URL",
    "OPENAI_API_KEY": "OPENAI_API_KEY",
}

def access_secret_version(secret_id, version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/496790449236/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode('UTF-8')

def init_secrets():    
    env = os.getenv("ENV", "DEV")
    logger.debug(f"Initializing secrets for environment: {env}")
    if env == "PROD" or env == "STG":
        """Initialize environment variables concurrently"""
        executor = ThreadPoolExecutor()
        futures = {}
        
        # Validate environment first
        if env not in ("PROD", "STG"):
            raise ValueError(f"Invalid ENV: {env}. Must be PROD or STG")
        
        # Load secrets concurrently
        for env_var, secret_suffix in SECRET_MAP.items():
            secret_id = f"SN_{env}_{secret_suffix}"
            futures[env_var] = executor.submit(
                access_secret_version, 
                secret_id=secret_id,
                version_id="latest"
            )
        
        # Set environment variables
        for env_var, future in futures.items():
            try:
                value = future.result()
                os.environ[env_var] = value
                logger.debug(f"Set {env_var} from secret {secret_id}")
            except Exception as e:
                logger.error(f"Failed to load secret for {env_var}: {e}")
                raise
    else:
        print("Loading secrets for DEV environment")
        # For DEV, set environment variables directly from the local .env file
        logger.debug("Loading secrets from local .env file")
        from dotenv import load_dotenv
        load_dotenv()
        
    # Post-validation
    required_vars = [
        "AUTH0_ALGORITHMS",
        "AUTH0_API_AUDIENCE",
        "API_KEY",
        "AUTH0_DOMAIN",
        "AUTH0_ISSUER",
        "API_BASE_URL",
        "OPENAI_API_KEY"
    ]
    for var in required_vars:
        if not os.getenv(var):
            raise EnvironmentError(f"Missing required environment variable: {var}")
    
    logger.info("Successfully initialized all secrets")