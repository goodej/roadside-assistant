import json
import os

import googlemaps

# local development only
if os.path.exists(r"..\ignore"):
    with open(os.path.abspath(r"..\ignore\ece528-roadside-maps.json")) as f:
        api_info = json.load(f)
    MAPS_API_KEY = api_info['MAPS_API_KEY']
    gmaps = googlemaps.Client(key=MAPS_API_KEY)
else:
    gmaps = googlemaps.Client()


# ---- General Utilities --------------------------------------------- #

def save_json(fp, d: dict):
    make_dir_if_not_existing(fp)
    with open(fp, 'w') as f:
        json.dump(d, f, indent=4)

def make_dir_if_not_existing(fp):
    pdir = os.path.dirname(fp)
    if not os.path.exists(pdir):
        os.mkdir(pdir)


# ---- Google Maps API ------------------------------------------------ #

def geocode(input):
    response = gmaps.geocode(input)[0]
    fields = ["formatted_address", "place_id"]
    result = {k: v for k, v in response.items() if k in fields}
    result["lat"] = response["geometry"]["location"]["lat"]
    result["lng"] = response["geometry"]["location"]["lng"]
    return result

def get_user_location_url(geodata):
    return f"https://www.google.com/maps/embed/v1/place?key={MAPS_API_KEY}&q=place_id:{geodata['place_id']}"
