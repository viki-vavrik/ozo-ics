import requests
import os
import time
import re
import json
import uuid
from datetime import datetime
from icalendar import Calendar, Event
from unicodedata import normalize
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- KONFIGURACE ---
BASE_URL = "https://ozoostrava.cz/svoz2.php"
OUTPUT_DIR = "kalendare"
MAX_WORKERS = 10  # Bezpečný počet vláken pro server OZO
# Zde můžeš přidávat další obce do seznamu:
TARGET_OBCE = ["Ostrava", "Hladké Životice"] 

COLORS = {
    "bio": "#8B4513", "papír": "#0000FF", "plasty": "#FFFF00",
    "směsný odpad": "#000000", "sklo": "#008000", "singlestream": "#FFA500"
}

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS)
session.mount('https://', adapter)

def slugify(text):
    text = normalize('NFD', str(text)).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', text)

def get_json(params):
    try:
        r = session.get(BASE_URL, params=params, timeout=15)
        text = r.text.strip()
        if "Notice:" in text or "Warning:" in text or not text:
            return {}
        return r.json()
    except:
        return {}

def save_ics(path, events, title):
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
            waste_types = list(waste.keys()) if isinstance(waste, dict) else (waste if isinstance(waste, list) else [])
            for type_name in waste_types:
                if type_name.lower() in ["velikonoce", "vánoce"]: continue
                event = Event()
                event.add('summary', type_name)
                event.add('dtstart', date_obj.date())
                event.add('dtend', date_obj.date())
                event.add('dtstamp', now)
                event.add('categories', [type_name])
                uid_seed = f"{path}_{date_str}_{type_name}"
                event.add('uid', str(uuid.uuid5(uuid.NAMESPACE_DNS, uid_seed)))
                color = COLORS.get(type_name.lower())
                if color:
                    event.add('color', color)
                    event.add('x-apple-calendar-color', color)
                cal.add_component(event)
        except:
            continue
    with open(path, 'wb') as f:
        f.write(cal.to_ical())

def fetch_house_data(house_info):
    obec, obvod, ulice, id_domu, cisp = house_info
    svoz_data = get_json({"obvod": obvod, "ulice": ulice, "cisp": cisp, "druh": -1})
    
    if svoz_data and isinstance(svoz_data, dict):
        file_rel_path = f"{OUTPUT_DIR}/{slugify(obec)}/{slugify(obvod)}/{slugify(ulice)}/{cisp}.ics"
        title = f"Svoz {obec}, {ulice} {cisp}"
        save_ics(file_rel_path, svoz_data, title)
        return {"obec": obec, "obvod": obvod, "ulice": ulice, "cislo": cisp, "path": file_rel_path}
    return None

def run():
    start_time = time.time()
    print(f"--- START GENERÁTORU PRO OBCE: {', '.join(TARGET_OBCE)} ---")
    init_data = get_json({"init": 1})
    if not init_data: 
        print("Chyba: Nepodařilo se načíst úvodní data.")
        return

    # 1. KROK: Nasbíráme všechny ulice pro vybrané obce
    all_streets = []
    for obec_name in TARGET_OBCE:
        if obec_name in init_data['obce']:
            print(f"Hledám obvody v: {obec_name}...")
            obvody = get_json({"druh": -1, "obec": obec_name})
            obvody_list = obvody if isinstance(obvody, list) else (obvody.keys() if isinstance(obvody, dict) else [])
            
            for obvod_name in obvody_list:
                print(f"  - Načítám ulice pro obvod: {obvod_name}")
                ulice_data = get_json({"druh": -1, "obec": obec_name, "obvod": obvod_name})
                if not ulice_data: ulice_data = {obvod_name: obvod_name}
                ulice_dict = ulice_data if isinstance(ulice_data, dict) else {u: u for u in ulice_data}
                for u_val in ulice_dict.values():
                    all_streets.append((obec_name, obvod_name, u_val))
        else:
            print(f"Varování: Obec {obec_name} nebyla v seznamu OZO nalezena.")

    # 2. KROK: Nasbíráme všechna čísla popisná
    print(f"\nNalezeno {len(all_streets)} ulic celkem. Hledám čísla popisná...")
    all_houses_to_fetch = []
    
    def get_houses_in_street(s):
        obec, obvod, ulice = s
        cisla = get_json({"druh": -1, "obec": obec, "obvod": obvod, "ulice": ulice, "mgr": 0})
        if isinstance(cisla, dict):
            return [(obec, obvod, ulice, id_d, d.get('ov', id_d)) for id_d, d in cisla.items()]
        return []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_street = {executor.submit(get_houses_in_street, s): s for s in all_streets}
        for future in as_completed(future_to_street):
            all_houses_to_fetch.extend(future.result())

    # 3. KROK: Stažení dat svozu a tvorba .ics (paralelně)
    print(f"\nNalezeno {len(all_houses_to_fetch)} domů. Generuji kalendáře...")
    catalog = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_house = {executor.submit(fetch_house_data, h): h for h in all_houses_to_fetch}
        for i, future in enumerate(as_completed(future_to_house)):
            res = future.result()
            if res: catalog.append(res)
            if i % 200 == 0:
                print(f"Pokrok: {i}/{len(all_houses_to_fetch)} domů hotovo...", end="\r")

    # 4. KROK: Seřazení katalogu pro konzistentní index.json
    print("\n\nŘadím katalog adres...")
    catalog.sort(key=lambda x: (x['obec'], x['obvod'], x['ulice'], x['cislo']))

    with open("index.json", "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    end_time = time.time()
    duration = (end_time - start_time) / 60
    print(f"\n--- HOTOVO ---")
    print(f"Celkem vytvořeno: {len(catalog)} kalendářů")
    print(f"Doba běhu: {duration:.2f} minut")

if __name__ == "__main__":
    run()
