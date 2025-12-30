import requests
import os
import time
import re
import json
import uuid
from datetime import datetime
from icalendar import Calendar, Event
from unicodedata import normalize

# Konfigurace
BASE_URL = "https://ozoostrava.cz/svoz2.php"
OUTPUT_DIR = "kalendare"

# Barvy (většina kalendářů je ignoruje, ale standard je dovoluje)
COLORS = {
    "bio": "#8B4513",             # Hnědá
    "papír": "#0000FF",           # Modrá
    "plasty": "#FFFF00",          # Žlutá
    "směsný odpad": "#000000",    # Černá
    "sklo": "#008000",            # Zelená
    "singlestream": "#FFA500"     # Oranžová
}

def slugify(text):
    """Převede text na bezpečné jméno souboru/složky."""
    text = normalize('NFD', str(text)).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', text)

def get_json(params):
    """Robustní načítání JSONu z API s ošetřením chyb."""
    try:
        r = requests.get(BASE_URL, params=params, timeout=15)
        text = r.text.strip()
        # Ignorujeme PHP chyby, které server OZO občas posílá do výstupu
        if "Notice:" in text or "Warning:" in text or not text:
            return {}
        return r.json()
    except Exception:
        return {}

def save_ics(path, events, title):
    """Vytvoří .ics soubor se všemi náležitostmi (UID, DTSTAMP, COLOR, CATEGORIES)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    cal = Calendar()
    cal.add('prodid', '-//OZO Svoz Odpadu//CZ')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', title)
    cal.add('method', 'PUBLISH')

    now = datetime.now()

    for date_str, waste in events.items():
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            
            # Zpracování typů odpadu (může být dict nebo list)
            waste_types = []
            if isinstance(waste, dict):
                waste_types = list(waste.keys())
            elif isinstance(waste, list):
                waste_types = waste

            for type_name in waste_types:
                # Přeskakujeme svátky a neznámé záznamy, chceme jen svoz
                if type_name.lower() in ["velikonoce", "vánoce"]:
                    continue

                event = Event()
                event.add('summary', type_name)
                event.add('dtstart', date_obj.date())
                event.add('dtend', date_obj.date()) # Celodenní událost
                event.add('dtstamp', now)
                
                # Kategorie pomáhají s barvami v Outlooku a Apple Calendar
                event.add('categories', [type_name])
                
                # Deterministické UID: stejná adresa + datum + druh = stejné ID
                uid_seed = f"{path}_{date_str}_{type_name}"
                event.add('uid', str(uuid.uuid5(uuid.NAMESPACE_DNS, uid_seed)))
                
                # Přidání barev (pokud je systém podporuje)
                color = COLORS.get(type_name.lower())
                if color:
                    event.add('color', color)
                    event.add('x-apple-calendar-color', color)

                cal.add_component(event)
        except Exception:
            continue
            
    # Uložíme soubor (přepíše stávající)
    with open(path, 'wb') as f:
        f.write(cal.to_ical())

def run():
    print("--- START GENEROVÁNÍ OZO KALENDÁŘŮ ---")
    init_data = get_json({"init": 1})
    if not init_data or 'obce' not in init_data:
        print("Kritická chyba: Nepodařilo se načíst seznam obcí.")
        return

    catalog = [] # Pro vytvoření indexu všech adres

    for obec_name in init_data['obce'].keys():
        # --- TESTOVACÍ FILTR ---
        # Pokud chceš generovat vše, následující řádek smaž nebo zakomentuj:
        #if obec_name not in [""]: continue
        
        print(f"\nZpracovávám obec: {obec_name}")
        obvody = get_json({"druh": -1, "obec": obec_name})
        obvody_list = obvody if isinstance(obvody, list) else obvody.keys()

        for obvod_name in obvody_list:
            ulice_data = get_json({"druh": -1, "obec": obec_name, "obvod": obvod_name})
            
            # Pokud obec nemá definované ulice, použijeme název obvodu
            if not ulice_data:
                ulice_data = {obvod_name: obvod_name}
            
            ulice_dict = ulice_data if isinstance(ulice_data, dict) else {u: u for u in ulice_data}

            for ulice_key, ulice_val in ulice_dict.items():
                print(f"  - Ulice: {ulice_val} ", end="\r")
                cisla = get_json({"druh": -1, "obec": obec_name, "obvod": obvod_name, "ulice": ulice_val, "mgr": 0})
                
                if not isinstance(cisla, dict):
                    continue

                for id_domu, dily in cisla.items():
                    # 'ov' je obvykle číslo popisné
                    cisp = dily.get('ov', id_domu)
                    svoz_data = get_json({"obvod": obvod_name, "ulice": ulice_val, "cisp": cisp, "druh": -1})
                    
                    if svoz_data and isinstance(svoz_data, dict):
                        file_rel_path = f"{OUTPUT_DIR}/{slugify(obec_name)}/{slugify(obvod_name)}/{slugify(ulice_val)}/{cisp}.ics"
                        title = f"Svoz {obec_name}, {ulice_val} {cisp}"
                        
                        save_ics(file_rel_path, svoz_data, title)
                        
                        # Přidáme do katalogu pro pozdější vyhledávání
                        catalog.append({
                            "obec": obec_name,
                            "obvod": obvod_name,
                            "ulice": ulice_val,
                            "cislo": cisp,
                            "path": file_rel_path
                        })
                
                # Malá pauza, abychom šetřili server OZO
                time.sleep(0.05)

    # Uložíme katalog všech vytvořených kalendářů
    with open("index.json", "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"\n\n--- HOTOVO ---")
    print(f"Vytvořeno záznamů: {len(catalog)}")
    print(f"Data uložena v: ./{OUTPUT_DIR}/")
    print(f"Katalog vytvořen v: ./index.json")

if __name__ == "__main__":
    run()
