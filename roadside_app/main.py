from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response
from turbo_flask import Turbo
import json
import os
import base64
from datetime import datetime
import uuid
import google.auth
from google.cloud import storage, pubsub_v1
from itsdangerous import base64_decode
import random
import threading
import time

from app_helper import helper


# ---- ENV variables --------------------------------------------------- #

# local only
if os.path.exists(r"../ignore"):
    os.environ['GRPC_DEFAULT_SSL_ROOTS_FILE_PATH_ENV_VAR'] = os.path.abspath(r"../ignore/ca_cert.pem")

# deploy
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.abspath(r"./env/ece528-roadside-35eaaf122e30.json")
credentials, project = google.auth.default()

posts = dict()

# ---- Flask App routing ----------------------------------------------- #

app = Flask(__name__)
turbo = Turbo(app)

# @app.before_first_request
# def before_first_request():
#     threading.Thread(target=update_load).start()


@app.route('/', methods=['GET', 'POST'])
def home():
    return render_template('home.html')


@app.route('/dialogue', methods=['GET', 'POST'])
def dialogue():
    if request.method == 'POST':
        r = request.get_json()
        user_info = {}
        fields = ['name', 'location', 'service']
        user_info = {k: v for k, v in r.items() if k in fields}

        if turbo.can_stream():
            return turbo.stream(
                turbo.append(render_template('loadavg.html', load=user_info), target='load'),
            )

    if request.method == 'GET':
        
        return render_template('dialogue.html', infos={})

    

@app.route('/request_made', methods=['GET', 'POST'])
def request_made():
    if request.method == 'POST':
        # save user request info to dict
        user_info = {}
        submission_id = str(uuid.uuid4())
        user_info['uuid'] = submission_id
        form_fields = ['first_name', 'last_name', 'location', 'issue']
        for field in form_fields:
            user_info[field] = request.form[field]
        
        user_info['geodata'] = helper.geocode(user_info['location'])

        # temporarily store as json
        # upload_to_cloud_storage(user_info, submission_id)
        # publish_message(topic="roadside-requests", msg=json.dumps(user_info))

        value = request.form.get("issue")
        print(f'value: {value}')
        value_utf_encoded = value.encode('utf-8')
        print(f'value w/ utf8 encoding: {value_utf_encoded}')
        value_b64 = base64.b64encode(value_utf_encoded)
        print(f'value b64 encoded: {value_b64}')
        value_b64_utf_decoded = value_b64.decode('utf-8')
        print(f'value b64 & utf8 decoded: {value_b64_utf_decoded}')


        user_location_url = helper.get_user_location_url(user_info['geodata'])
        places_nearby = helper.get_places_nearby(user_info["geodata"], user_info["issue"])
        most_prominent = places_nearby[0]
        top_place = helper.get_place_details(place_id=most_prominent['place_id'])

        # helper.save_json(f'submissions\{submission_id}.json', user_info)
        return render_template('request_made.html', infos=user_info, user_location_url=user_location_url, places_nearby=places_nearby, top_place=top_place)



    if request.method == 'GET':
        return redirect(url_for('home'))

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "POST":
        # posts[f'post_{datetime.now().strftime("%Y/%m/%d %H:%M:%S")}'] = request.get_json()
        # helper.save_json(f'submissions\posts.json', posts)

        fulfillment = handle_request()

        return make_response(jsonify(fulfillment))

    if request.method == "GET":
        return "Hello webhook test!"


# @app.context_processor
# def inject_user_info(user_info):
#     load = [int(random.random() * 100) / 100 for _ in range(3)]
#     user_info = {'name': load[0], "location": f"{load[2]} Main St", "service": f"{load[2]} gallons fuel"}
#     return user_info

@app.context_processor
def cache_user_info():
    if session.get('user_info') is None:
        return {}
    # load = [int(random.random() * 100) for _ in range(3)]
    # user_info = {'name': load[0], "location": f"{load[2]} Main St", "service": f"{load[2]} gallons fuel"}
    else:
        return session['user_info']


# ---- DialogFlow Webhook --------------------------------------------- #

def handle_request():
    entity_res = dict()
    r = request.get_json()
    
    df_session = r.get("session").split("/")[-1]

    # load df session cache
    service_info = helper.download_from_cloud_storage(df_session)
    
    action = r.get("queryResult").get("action")

    if action == "service.get_top_provider":
        service_info.update(parse_service_followup(r))

        # geocode provided user location
        service_info["geodata"] = helper.geocode(service_info.get("location"))
        user_location_url = helper.get_user_location_url(service_info['geodata'])

        # find relevant service providers nearby & choose
        places_nearby = helper.get_places_nearby(service_info["geodata"], service_info["service"])
        most_prominent = places_nearby[0]
        top_place = helper.get_place_details(place_id=most_prominent['place_id'])
        
        # update service info
        service_info['places_nearby'] = places_nearby
        service_info["prominence_index"] = 0
        service_info["selected_provider"] = top_place

        # entity_res = {
        #     "sessionEntityTypes": [
        #         {
        #             "name": r["session"] + "/entityTypes/" + "company",
        #             "entities":[
        #                 {
        #                 "value": top_place['name'],
        #                 },
        #             ],
        #             "entityOverrideMode":"ENTITY_OVERRIDE_MODE_OVERRIDE"
        #         }
        #     ]
        # }

        if not top_place["name"]:
            print('no top places found')

        msg1 = f'{top_place["name"]} is within a few miles of your location'
        if top_place.get("rating"):
            msg2 = f' and has a rating of {top_place["rating"]}'
        else:
            msg2 = ""

        res =  f'{msg1}{msg2}. [{top_place["website"]}] Would you like me to contact them for you?'
        
        
    elif action == "service.notify_company":
        company = service_info["selected_provider"]
        phone_msg = ''
        if company.get("formatted_phone_number"):
            phone_msg = f' You can reach them at {company["formatted_phone_number"]} in the meantime if you have any questions.'
        res = f'I have notified {company["name"]} you need {service_info["service"]}.  They will contact you soon with their estimated arival time.{phone_msg}'
    
    elif action == "service.get_different_provider":
        service_info["prominence_index"] += 1
        new_option = service_info["places_nearby"][service_info["prominence_index"]]
        print(f'Getting details for {new_option["name"]} w/ id: {new_option["place_id"]}.')
        new_place = helper.get_place_details(place_id=new_option['place_id'])

        # update service info
        service_info["selected_provider"] = new_place

        msg1 = f'{new_place["name"]} is within a few miles of your location'
        if new_place.get("rating"):
            msg2 = f' and has a rating of {new_place["rating"]}'
        else:
            msg2 = ""

        res =  f'{msg1}{msg2}. [{new_place["website"]}] Would you like me to contact them for you?'
    
    else:
        res = f'Unconfigured action {action}.'

    helper.upload_to_cloud_storage(service_info, destination_blob_name=df_session)
    session['user_info'] = {'service': service_info['service'], 'name': service_info['name'], 'location': service_info['location']}
    cache_user_info()
    return {'fulfillmentText': res}


def get_output_context(r, context):
    session_path = r["session"] + "/contexts/"
    for item in r.get("queryResult").get("outputContexts"):
        if item.get("name") == session_path + context:
            return item

def parse_service_followup(r):
    result = dict()
    service_followup = get_output_context(r, "service-followup")
    result["service"] = service_followup["parameters"]["service"]
    result["location"] = service_followup["parameters"]["location.original"]
    result["name"] = service_followup["parameters"]["person.original"]
    return result

def update_load():
    with app.app_context():
        turbo.push(turbo.replace(render_template('loadavg.html'), 'load'))