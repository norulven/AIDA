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

    def get_all_entities(self) -> List[Dict]:
        """Gets a flat list of all available entities."""
        if not self._ensure_connected():
            return []

        all_entities = []
        try:
            entities = self.client.get_entities()
            for group in entities.values():
                for entity in group.values():
                    # Add useful metadata
                    data = entity.state.as_dict()
                    data['entity_id'] = entity.entity_id
                    data['domain'] = entity.domain
                    all_entities.append(data)
            return all_entities
        except Exception as e:
            logger.error(f"Error getting entities: {e}")
            return []

    def search_entities(self, query: str) -> List[Dict]:
        """Search for entities by name or ID."""
        query = query.lower()
        matches = []
        
        for entity in self.get_all_entities():
            entity_id = entity.get('entity_id', '').lower()
            friendly_name = entity.get('attributes', {}).get('friendly_name', '').lower()
            
            if query in entity_id or query in friendly_name:
                matches.append(entity)
                
        return matches

    def find_entity_by_name(self, friendly_name_query: str) -> Optional[str]:
        """Finds an entity's ID by its friendly name."""
        matches = self.search_entities(friendly_name_query)
        
        if not matches:
            logger.warning(f"No entity found for query: {friendly_name_query}")
            return None
            
        # If exact match on friendly name, prefer that
        for entity in matches:
            if entity.get('attributes', {}).get('friendly_name', '').lower() == friendly_name_query.lower():
                logger.info(f"Found exact match '{entity['entity_id']}' for '{friendly_name_query}'")
                return entity['entity_id']
                
        # Otherwise return the first match (assumed best guess)
        # TODO: Could add smarter ranking/fuzzy matching here
        best_match = matches[0]
        logger.info(f"Found entity '{best_match['entity_id']}' for query '{friendly_name_query}'")
        return best_match['entity_id']
