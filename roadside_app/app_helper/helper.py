import json
import os
import requests

import google.auth
from google.cloud import storage
import googlemaps


# ---- Parameters ----------------------------------------------------- #

RADIUS = 1609 # meters


# ---- ENV variables -------------------------------------------------- #

# deploy

# Maps API
with open(os.path.abspath(r"./env/ece528-roadside-maps.json")) as f:
    api_info = json.load(f)
MAPS_API_KEY = api_info['MAPS_API_KEY']
gmaps = googlemaps.Client(key=MAPS_API_KEY)

# GCP
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.abspath(r"./env/ece528-roadside-35eaaf122e30.json")
credentials, project = google.auth.default()
storage_client = storage.Client()
bucket = storage_client.bucket("roadside-cache")


# ---- General Utilities ---------------------------------------------- #

def save_json(fp, d: dict):
    make_dir_if_not_existing(fp)
    with open(fp, 'w') as f:
        json.dump(d, f, indent=4)

def make_dir_if_not_existing(fp):
    pdir = os.path.dirname(fp)
    if not os.path.exists(pdir):
        os.mkdir(pdir)

def to_plus_str(s: str) -> str:
    return "+".join(s.split(" "))

def load_cache(session):
    session_path = r"submissions/{}.json".format(session)
    make_dir_if_not_existing(session_path)
    if os.path.exists(session_path):
        return json.load(open(session_path))
    else:
        return dict()

def save_cache(session, d):
    session_path = r"submissions/{}.json".format(session)
    with open(session_path, 'w') as f:
        json.dump(d, f, indent=4)

def upload_to_cloud_storage(item:dict, destination_blob_name):
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(json.dumps(item))

def download_from_cloud_storage(blob_name:str) -> dict:
    blob = bucket.blob(blob_name)
    if blob.exists():
        return json.loads(blob.download_as_string())
    else:
        return dict()


# ---- Google Maps API ------------------------------------------------ #

def geocode(input: str) -> dict:
    response = gmaps.geocode(input)[0]
    fields = ["formatted_address", "place_id"]
    result = {k: v for k, v in response.items() if k in fields}
    result["lat"] = response["geometry"]["location"]["lat"]
    result["lng"] = response["geometry"]["location"]["lng"]
    result["lat_long"] = (result["lat"], result["lng"])
    return result

def get_user_location_url(geodata: dict) -> str:
    return f"https://www.google.com/maps/embed/v1/place?key={MAPS_API_KEY}&q=place_id:{geodata['place_id']}"

def get_places_nearby(geodata: dict, keywords: str) -> list:
    response = gmaps.places_nearby(
        location=geodata["lat_long"], 
        keyword=to_plus_str(keywords), 
        radius=RADIUS, 
        language='en', 
        type="car_repair"
        )
    if response["status"] == "OK":
        return response["results"]
    else:
        return [response["status"]]

def get_place_details(place_id: str) -> dict:
    url = "https://maps.googleapis.com/maps/api/place/details/json?"
    fields = ["name", "formatted_address", "formatted_phone_number", "website", "rating"]

    params = {
        "place_id": place_id,
        "key": MAPS_API_KEY,
        "fields": ",".join(fields)
    }
    
    resp = requests.get(url, params=params)
    if resp.status_code == 200:
        return resp.json()["result"]
    else:
        return {'status': resp.status_code}
