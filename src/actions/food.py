import requests
import logging
import json
import base64
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import ollama
from src.vision.camera import Camera

# URL til Aida-Kitchen (kjører lokalt eller på nettverket)
# Siden Aida kjører på samme maskin som containeren/serveren foreløpig, bruker vi localhost.
KITCHEN_API_URL = "http://localhost:8000"

logger = logging.getLogger("aida.actions.food")

def add_item_to_inventory(name: str, quantity: float, unit: str, location: str = "Kjøkken"):
    """
    Legger til en vare direkte i lageret.
    """
    endpoint = f"{KITCHEN_API_URL}/inventory/add"
    # Endepunktet forventer Form-data
    data = {
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "location": location
    }
    try:
        response = requests.post(endpoint, data=data)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to add item {name}: {e}")
        return False

def scan_receipt():
    """
    Aktiverer webkameraet, tar bilde av en kvittering, tolker varene, og legger dem til i lageret.
    Bruk denne når brukeren holder opp en kvittering og sier "skann denne" eller "legg til varene fra kvitteringen".
    """
    # 1. Ta bilde
    cam = Camera()
    try:
        cam.open()
        # Gi kameraet et sekund til å justere lys
        import time
        time.sleep(1.0) 
        image_base64 = cam.get_frame_base64()
    except Exception as e:
        return f"Klarte ikke starte kameraet: {e}"
    finally:
        cam.close()

    if not image_base64:
        return "Klarte ikke ta bilde."

    # 2. Analyser med Vision AI (Llava/Llama-vision)
    # Vi antar at modellen 'llava:7b' er installert (eller konfigurert i config).
    vision_model = 'llava:7b' 
    
    prompt = """
    Analyze this receipt image carefully. Identify all food/grocery items.
    Ignore prices, totals, taxes, and store info.
    
    Output a valid JSON list of objects. Each object must have:
    - "name": The name of the item (Translate to Norwegian if possible, e.g. "Milk" -> "Melk").
    - "quantity": The numeric quantity (default to 1.0 if not specified).
    - "unit": The unit (e.g. "stk", "kg", "l", "pk"). If unsure, use "stk".
    
    Example JSON:
    [
        {"name": "Melk", "quantity": 1.0, "unit": "l"},
        {"name": "Egg", "quantity": 12.0, "unit": "stk"}
    ]
    
    Output ONLY the JSON.
    """
    
    logger.info("Sender kvittering til AI-analyse...")
    try:
        response = ollama.chat(
            model=vision_model,
            messages=[{
                'role': 'user',
                'content': prompt,
                'images': [image_base64]
            }]
        )
        content = response['message']['content']
        
        # 3. Parse JSON
        start = content.find('[')
        end = content.rfind(']') + 1
        if start == -1 or end == 0:
            return "Klarte ikke lese kvitteringen (fikk ikke JSON-data fra AI-en)."
            
        json_str = content[start:end]
        items = json.loads(json_str)
        
        # 4. Legg til i lageret
        added = []
        failed = []
        for item in items:
            name = item.get('name')
            qty = float(item.get('quantity', 1.0))
            unit = item.get('unit', 'stk')
            
            if add_item_to_inventory(name, qty, unit):
                added.append(f"{name} ({qty} {unit})")
            else:
                failed.append(name)
        
        result_text = f"Ferdig! La til {len(added)} varer:\n" + "\n".join(added)
        if failed:
            result_text += f"\n\nKlarte ikke legge til: {', '.join(failed)}"
            
        return result_text

    except Exception as e:
        logger.error(f"Receipt scanning failed: {e}")
        return f"Noe gikk galt under skanningen: {e}"

def import_recipe_from_url(url: str):
    """
    Laster ned en oppskrift fra en nettside (URL), tolker innholdet med AI, og lagrer den i kjøkken-databasen.
    
    Args:
        url (str): Adressen til nettsiden med oppskriften.
    """
    try:
        # 1. Hent nettsiden
        logger.info(f"Henter oppskrift fra {url}...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # 2. Trekk ut tekst
        soup = BeautifulSoup(response.text, 'html.parser')
        # Fjern script og style
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
        text = soup.get_text(separator=' ', strip=True)
        # Begrens lengden for å ikke sprenge context window
        text = text[:8000]
        
        # 3. Bruk AI til å strukturere dataene
        prompt = f"""
        Extract the cooking recipe from the text below and format it as valid JSON.
        The JSON must match this structure exactly:
        {{
            "name": "Recipe Name",
            "description": "Short description",
            "instructions": "Full step-by-step instructions as a single string",
            "ingredients": [
                {{"name": "ingredient name", "quantity": 1.0, "unit": "kg/g/dl/l/stk/ts/ss"}}
            ]
        }}
        
        Rules:
        - Translate ingredients to Norwegian if possible (e.g. "Flour" -> "Hvetemel").
        - Convert fractions to decimals (1/2 -> 0.5).
        - If unit is missing, use "stk" or leave blank.
        - Output ONLY the JSON, nothing else.

        Text to parse:
        {text}
        """
        
        logger.info("Analyserer oppskrift med AI...")
        # Vi bruker en rask modell hvis tilgjengelig, ellers default fra systemet
        # Vi antar 'llama3.1:8b' er tilgjengelig basert på config
        llm_response = ollama.chat(model='llama3.1:8b', messages=[{'role': 'user', 'content': prompt}])
        content = llm_response['message']['content']
        
        # 4. Finn og parse JSON
        # Noen ganger prater modellen litt før/etter JSON, så vi klipper ut
        start = content.find('{')
        end = content.rfind('}') + 1
        if start == -1 or end == 0:
            return "Klarte ikke tolke oppskriften (fikk ikke gyldig data fra AI)."
            
        json_str = content[start:end]
        recipe_data = json.loads(json_str)
        
        # 5. Lagre via den eksisterende funksjonen vår (men direkte mot API for å spare et kall)
        return add_recipe_to_kitchen(
            name=recipe_data['name'],
            description=recipe_data.get('description', ''),
            instructions=recipe_data.get('instructions', ''),
            ingredients=recipe_data.get('ingredients', [])
        )

    except Exception as e:
        logger.error(f"Import failed: {e}")
        return f"Kunne ikke importere oppskriften: {e}"

def add_recipe_to_kitchen(name: str, description: str, instructions: str, ingredients: list):
    """
    Legger til en ny matoppskrift i det digitale kjøkkenet. Bruk denne når brukeren vil lagre en oppskrift de har funnet eller diktert.
    
    Args:
        name (str): Navnet på retten (f.eks. "Pannekaker").
        description (str): En kort beskrivelse av retten.
        instructions (str): Fullstendig fremgangsmåte for å lage retten.
        ingredients (list): En liste med ingredienser, hver ingrediens er en dict med 'name' (str), 'quantity' (float), og 'unit' (str, f.eks. 'g', 'dl', 'stk').
    """
    endpoint = f"{KITCHEN_API_URL}/api/recipes"
    
    payload = {
        "name": name,
        "description": description,
        "instructions": instructions,
        "ingredients": ingredients
    }
    
    try:
        logger.info(f"Sender oppskrift '{name}' til Aida Kitchen...")
        response = requests.post(endpoint, json=payload)
        response.raise_for_status()
        return f"Suksess! Oppskriften '{name}' er lagret i kjøkken-databasen."
    except requests.exceptions.ConnectionError:
        return "Feil: Får ikke kontakt med Aida Kitchen (serveren kjører kanskje ikke?)."
    except Exception as e:
        logger.error(f"Feil ved lagring av oppskrift: {e}")
        return f"Noe gikk galt: {e}"

from datetime import datetime, timedelta

# ... (eksisterende imports)

def get_inventory_list(category: str = "all"):
    """
    Henter en oversikt over alle matvarer som finnes i lageret/kjøleskapet.
    
    Args:
        category (str): Hvilken kategori man vil sjekke (f.eks. "Kjøl", "Frys", "Tørrvare", eller "all" for alt). Standard er "all".
    """
    endpoint = f"{KITCHEN_API_URL}/api/inventory"
    try:
        response = requests.get(endpoint)
        response.raise_for_status()
        items = response.json()
        
        if not items:
            return "Lageret er tomt."
            
        # Filtrer hvis kategori er spesifisert og ikke er "all"
        if category and category.lower() != "all":
            filtered_items = [
                i for i in items 
                if category.lower() in i['location'].lower() 
                or (i.get('category') and category.lower() in i.get('category').lower())
            ]
            
            if not filtered_items:
                return f"Fant ingen varer i kategorien '{category}'."
            items = filtered_items

        # Formater teksten fint for Aida
        text = "Her er lagerbeholdningen:\n"
        for item in items:
            text += f"- {item['item']}: {item['quantity']} {item['unit']} ({item['location']})\n"
        return text
        
    except Exception as e:
        logger.error(f"Feil ved henting av lager: {e}")
        return "Klarte ikke sjekke lageret akkurat nå."

def get_recipes_list():
    """
    Henter en liste over alle lagrede oppskrifter i databasen. 
    Bruk denne for å se hvilke retter som er tilgjengelige for planlegging.
    """
    endpoint = f"{KITCHEN_API_URL}/recipes" # Vi kan hente HTML-siden eller lage et API.
    # La oss bruke API-et vi har i main.py (som jeg må sjekke om finnes)
    # Jeg legger til et API-endepunkt i Kitchen for dette nå.
    endpoint = f"{KITCHEN_API_URL}/api/recipes_list"
    try:
        response = requests.get(endpoint)
        response.raise_for_status()
        recipes = response.json()
        if not recipes:
            return "Ingen oppskrifter er lagret ennå."
        
        text = "Her er de lagrede oppskriftene:\n"
        for r in recipes:
            text += f"- {r['name']} (ID: {r['id']})\n"
        return text
    except Exception as e:
        return f"Klarte ikke hente oppskriftslisten: {e}"

def get_recipe_details(recipe_name: str):
    """
    Henter detaljert informasjon om en oppskrift (ingredienser og fremgangsmåte).
    Bruk denne når brukeren spør hvordan man lager noe, eller hva de trenger for å lage en rett.
    
    Args:
        recipe_name (str): Navnet på retten (f.eks. "Pannekaker").
    """
    try:
        # 1. Finn ID basert på navn
        r_list = requests.get(f"{KITCHEN_API_URL}/api/recipes_list").json()
        
        recipe_id = None
        # Eksakt match først
        for r in r_list:
            if r['name'].lower() == recipe_name.lower():
                recipe_id = r['id']
                break
        
        # Delvis match hvis ikke eksakt
        if not recipe_id:
            for r in r_list:
                if recipe_name.lower() in r['name'].lower():
                    recipe_id = r['id']
                    break
        
        if not recipe_id:
            return f"Fant ingen oppskrift med navnet '{recipe_name}'."

        # 2. Hent detaljer
        details = requests.get(f"{KITCHEN_API_URL}/api/recipe/{recipe_id}").json()
        
        if "error" in details:
            return "Noe gikk galt ved henting av oppskriften."

        # 3. Formater svaret pent
        text = f"Oppskrift: {details['name']}\n"
        if details.get('description'):
            text += f"Beskrivelse: {details['description']}\n"
        
        text += "\nIngredienser:\n"
        for ing in details['ingredients']:
            text += f"- {ing['quantity']} {ing['unit']} {ing['name']}\n"
            
        text += "\nFremgangsmåte:\n"
        text += details['instructions']
        
        return text

    except Exception as e:
        return f"Feil ved henting av oppskrift: {e}"

def get_meal_plan(day: str = "today"):
    """
    Sjekker hva som står på matplanen for en gitt dag.
    
    Args:
        day (str): Dagen du vil sjekke. Kan være "today", "tomorrow", eller en dato "YYYY-MM-DD". Standard er "today".
    """
    target_date = datetime.now().date()
    if day.lower() == "tomorrow":
        target_date += timedelta(days=1)
    elif day.lower() != "today":
        try:
            target_date = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            return "Ugyldig datoformat. Bruk 'today', 'tomorrow' eller 'YYYY-MM-DD'."
            
    date_str = target_date.strftime("%Y-%m-%d")
    
    # Vi bruker samme API som kalenderen (GET /api/plan) men ber om bare én dag
    endpoint = f"{KITCHEN_API_URL}/api/plan?start_date={date_str}&end_date={date_str}"
    
    try:
        response = requests.get(endpoint)
        response.raise_for_status()
        plans = response.json()
        
        if not plans:
            return f"Det er ingen planer for {day} ({date_str})."
            
        plan = plans[0]
        dish = plan['recipe'] if plan['recipe'] else plan['note']
        return f"På {day} ({date_str}) er planen: {dish}."
        
    except Exception as e:
        logger.error(f"Feil ved henting av matplan: {e}")
        return "Klarte ikke sjekke matplanen."

def add_meal_to_plan(recipe_name: str, day: str = "today", note: str = None):
    """
    Legger til en middag i matplanen.
    
    Args:
        recipe_name (str): Navnet på oppskriften (må finnes i systemet) ELLER et fritekst-notat.
        day (str): Dagen å planlegge for ("today", "tomorrow", "YYYY-MM-DD").
        note (str): Et valgfritt notat.
    """
    target_date = datetime.now().date()
    if day.lower() == "tomorrow":
        target_date += timedelta(days=1)
    elif day.lower() != "today":
        try:
            target_date = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            return "Ugyldig datoformat."
            
    date_str = target_date.strftime("%Y-%m-%d")

    # Prøv å finn recipe_id
    recipe_id = None
    final_note = note
    
    try:
        # Hent alle oppskrifter
        r_list = requests.get(f"{KITCHEN_API_URL}/api/recipes_list").json()
        
        # Søk etter match (case-insensitive)
        found = False
        for r in r_list:
            if r['name'].lower() == recipe_name.lower():
                recipe_id = r['id']
                found = True
                break
        
        if not found:
            # Hvis vi ikke fant den eksakt, sjekk om navnet er "likt nok" (inneholder)
            # F.eks. "Spaghetti" matcher "Spaghetti Bolognese"
            for r in r_list:
                if recipe_name.lower() in r['name'].lower() or r['name'].lower() in recipe_name.lower():
                    recipe_id = r['id']
                    found = True
                    break
        
        if not found:
            # Hvis fortsatt ikke funnet, legg navnet i notatet hvis det ikke er der
            if not final_note:
                final_note = recipe_name
            else:
                final_note = f"{recipe_name} ({final_note})"

    except Exception as e:
        logger.error(f"Kunne ikke slå opp oppskrift: {e}")
        final_note = recipe_name

    payload = {
        "date": date_str,
        "meal_type": "Middag",
        "recipe_id": recipe_id,
        "note": final_note if not recipe_id else final_note
    }
    
    endpoint = f"{KITCHEN_API_URL}/api/plan"
    
    try:
        response = requests.post(endpoint, json=payload)
        response.raise_for_status()
        
        msg = f"Lagt til '{recipe_name}' i planen for {date_str}."
        if recipe_id:
            msg += " (Koblet til oppskrift)"
        else:
            msg += " (Som notat)"
        return msg
    except Exception as e:
        return f"Klarte ikke oppdatere planen: {e}"
        
    except Exception as e:
        logger.error(f"Feil ved henting av lager: {e}")
        return "Klarte ikke sjekke lageret akkurat nå."
