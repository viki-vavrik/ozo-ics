# OZO Ostrava svozový kalendář pro Home Assistant

### Požadavky
* Mít nainstalovanou integraci [Waste Collection Schedule](https://github.com/mampfes/hacs_waste_collection_schedule) (dostupná v HACS).
## Návod na přidání do Home Assistanta:
1. Z repozitáře si stáhněte soubor [`ozoostrava_cz.py`](https://github.com/viki-vavrik/ozo-ics/blob/main/ozoostrava_cz.py).
2. Vložte ho do složky `custom_components/waste_collection_schedule/waste_collection_schedule/source/`.
3. Teď máte dvě možnosti:
### Možnost A: Úprava souboru sources.json:
Tato cesta vám umožní přidávat a upravovat kalendář přes grafické rozhraní.
1. Najděte soubor `custom_components/waste_collection_schedule/waste_collection_schedule/sources.json`.
2. Vyhledejte sekci `"Czech Republic"` a přidejte do ní následující kód:
```json
    { 
      "title": "OZO Ostrava",
      "module": "ozoostrava_cz",
      "default_params": {},
      "id": "ozoostrava_cz"
    },

```
3. **Restartujte Home Assistant.**
4. Jděte do **Nastavení** -> **Zařízení a služby** -> **Přidat integraci**. (Settings -> Devices & services -> Add integration)
5. Vyberte `Waste Collection Schedule`, zvolte **Czech Republic** -> **OZO Ostrava** a nastavte si vaši adresu.
###  Možnost B: Úprava configuration.yaml:
  Více informací v [dokumentaci Waste Collection Schedule](https://github.com/mampfes/hacs_waste_collection_schedule/blob/master/doc/installation.md#configurationyaml).<br>
  příklad kódu:
```yaml
waste_collection_schedule:
  sources:
    - name: ozoostrava_cz
      args:
        obec: "Ostrava"
        obvod: "Poruba"
        ulice: "Hlavní třída"
        cislo: "583"
# Příklad senzoru:
sensor:
  - platform: waste_collection_schedule
    name: "Příští svoz"
    details_format: "upcoming"
```
**Poté restartujte Home Assistant.**

---
**Zdroj dat:** [ozoostrava.cz/svoz](https://ozoostrava.cz/svoz)

*Nemám nic společného se společností OZO Ostrava s.r.o.*

## 🇪🇺 English
Custom [Waste Collection Schedule](https://github.com/mampfes/hacs_waste_collection_schedule) source for Ostrava and nearby municipalities.
### Installation
1. Install [Waste Collection Schedule](https://github.com/mampfes/hacs_waste_collection_schedule) via HACS.
2. Upload [`ozoostrava_cz.py`](https://github.com/viki-vavrik/ozo-ics/blob/main/ozoostrava_cz.py) to: `custom_components/waste_collection_schedule/waste_collection_schedule/source/`
3. Restart Home Assistant and configure via UI (by editing sources.json) or via configuration.yaml as shown above.

**Data source:** [ozoostrava.cz/svoz](https://ozoostrava.cz/svoz)

*I am not affiliated with OZO Ostrava s.r.o.*
