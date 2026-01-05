"""Home Assistant client operations."""

import logging
from homeassistant_api import Client
from typing import Optional, List, Dict

from src.core.config import HomeAssistantConfig

# Configure logging
logger = logging.getLogger("aida.ha")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = logging.FileHandler('/tmp/aida_ha.log')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

class HomeAssistantClient:
    """Handles Home Assistant API connections."""

    def __init__(self, config: HomeAssistantConfig):
        self.config = config
        self.client: Optional[Client] = None
        logger.info("HomeAssistantClient initialized.")

    def _ensure_connected(self) -> bool:
        """Ensures connection to Home Assistant."""
        if not self.config.enabled:
            logger.warning("Home Assistant integration is not enabled.")
            return False
        if not self.config.url or not self.config.token:
            logger.error("Home Assistant URL or token not set.")
            return False

        if self.client:
            return True

        try:
            logger.info(f"Connecting to Home Assistant at: {self.config.url}")
            self.client = Client(self.config.url, self.config.token)
            logger.info("Successfully connected to Home Assistant.")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Home Assistant: {e}", exc_info=True)
            self.client = None
            return False

    def get_device_state(self, entity_id: str) -> Optional[Dict]:
        """Gets the state of a specific entity."""
        if not self._ensure_connected():
            return None
        
        try:
            entity = self.client.get_entity(entity_id=entity_id)
            if entity:
                logger.info(f"State for {entity_id}: {entity.state.state}")
                return entity.state.as_dict()
            return None
        except Exception as e:
            logger.error(f"Failed to get state for {entity_id}: {e}")
            return None
            
    def call_service(self, domain: str, service: str, service_data: Dict) -> bool:
        """Calls a service in Home Assistant."""
        if not self._ensure_connected():
            return False

        try:
            logger.info(f"Calling service {domain}.{service} with data: {service_data}")
            self.client.trigger_service(domain, service, **service_data)
            return True
        except Exception as e:
            logger.error(f"Failed to call service {domain}.{service}: {e}")
            return False
            
    def find_entity_by_name(self, friendly_name_query: str) -> Optional[str]:
        """Finds an entity's ID by its friendly name."""
        if not self._ensure_connected():
            return None
        
        friendly_name_query = friendly_name_query.lower()
        
        try:
            entities = self.client.get_entities()
            for group in entities.values():
                for entity in group.values():
                    friendly_name = entity.state.attributes.get("friendly_name", "").lower()
                    if friendly_name_query in friendly_name:
                        logger.info(f"Found entity '{entity.entity_id}' for query '{friendly_name_query}'")
                        return entity.entity_id
            
            logger.warning(f"No entity found for query: {friendly_name_query}")
            return None
        except Exception as e:
            logger.error(f"Error finding entity: {e}")
            return None
