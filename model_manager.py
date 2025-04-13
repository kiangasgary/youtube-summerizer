import logging
import time
from typing import Optional, Dict, Any
import google.generativeai as genai
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class ModelConfig:
    """Configuration for a single AI model."""
    def __init__(self, name: str, priority: int = 1, max_retries: int = 3):
        self.name = name
        self.model = None
        self.available = True
        self.quota_remaining = True
        self.retry_after: Optional[datetime] = None
        self.max_retries = max_retries
        self.priority = priority
        self.error_count = 0
        self.last_success: Optional[datetime] = None

class GoogleAIModelManager:
    """Manages multiple Google AI models with fallback logic."""
    
    def __init__(self, api_key: str):
        # Configure the API
        genai.configure(api_key=api_key)
        
        # Initialize model configurations
        self.models: Dict[str, ModelConfig] = {
            'gemini-2.5-pro-exp-03-25': ModelConfig(
                name='gemini-2.5-pro-exp-03-25',
                priority=1
            ),
            'gemini-1.5-pro': ModelConfig(
                name='gemini-1.5-pro',
                priority=2
            ),
            'gemini-pro': ModelConfig(
                name='gemini-pro',
                priority=3
            )
        }
        
        self.current_model_name = 'gemini-2.5-pro-exp-03-25'
        self.initialize_models()
        
        # Settings
        self.rate_limit_cooldown = 300  # 5 minutes
        self.error_threshold = 5  # Max errors before marking model as unavailable
        self.global_retry_delay = 5  # seconds between retries
    
    def initialize_models(self):
        """Initialize all models."""
        for model_name, config in self.models.items():
            try:
                config.model = genai.GenerativeModel(model_name)
                config.last_success = None
                logger.info(f"Successfully initialized {model_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize {model_name}: {str(e)}")
                config.available = False
                config.error_count += 1
    
    def get_next_available_model(self) -> Optional[str]:
        """Get the next available model based on priority and status."""
        now = datetime.now()
        available_models = []
        
        for name, config in self.models.items():
            # Skip if model is marked as unavailable
            if not config.available:
                continue
            
            # Skip if model is in cooldown
            if config.retry_after and now < config.retry_after:
                continue
            
            # Skip if quota is exceeded
            if not config.quota_remaining:
                continue
            
            available_models.append((name, config))
        
        if not available_models:
            return None
        
        # Sort by priority and last success (prefer models that worked recently)
        available_models.sort(key=lambda x: (
            x[1].priority,
            -1 if x[1].last_success is None else (now - x[1].last_success).total_seconds()
        ))
        
        return available_models[0][0]
    
    def handle_error(self, model_name: str, error: Exception) -> None:
        """Handle errors and update model status."""
        config = self.models[model_name]
        error_msg = str(error)
        
        if "quota" in error_msg.lower() or "429" in error_msg:
            logger.warning(f"{model_name} quota exceeded or rate limited")
            config.quota_remaining = False
            config.retry_after = datetime.now() + timedelta(seconds=self.rate_limit_cooldown)
        else:
            config.error_count += 1
            if config.error_count >= self.error_threshold:
                config.available = False
                logger.error(f"Disabled {model_name} due to too many errors")
    
    def reset_model_status(self, model_name: str) -> None:
        """Reset a model's error count and status after successful use."""
        config = self.models[model_name]
        config.error_count = 0
        config.last_success = datetime.now()
        config.quota_remaining = True
        config.retry_after = None
        config.available = True
    
    async def generate_content(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Generate content using available models with fallback."""
        attempts = 0
        last_error = None
        
        while attempts < max_retries:
            model_name = self.get_next_available_model()
            
            if not model_name:
                raise Exception(
                    "No available models found. Please try again later.\n"
                    f"Last error: {str(last_error) if last_error else 'Unknown'}"
                )
            
            try:
                logger.info(f"Attempting to generate content with {model_name}")
                response = self.models[model_name].model.generate_content(prompt)
                
                if response.text:
                    self.reset_model_status(model_name)
                    self.current_model_name = model_name
                    return response.text
                
            except Exception as e:
                last_error = e
                self.handle_error(model_name, e)
                logger.warning(f"Error with {model_name}: {str(e)}")
            
            attempts += 1
            if attempts < max_retries:
                time.sleep(self.global_retry_delay)
        
        raise Exception(f"All models failed after {max_retries} attempts. Last error: {str(last_error)}")
    
    def get_model_status(self) -> Dict[str, Dict[str, Any]]:
        """Get the current status of all models."""
        now = datetime.now()
        return {
            name: {
                "available": config.available,
                "quota_remaining": config.quota_remaining,
                "retry_after": str(config.retry_after) if config.retry_after else None,
                "error_count": config.error_count,
                "last_success": str(config.last_success) if config.last_success else None,
                "cooldown_remaining": str(config.retry_after - now) if config.retry_after and config.retry_after > now else None
            }
            for name, config in self.models.items()
        }
