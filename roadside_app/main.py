from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import os
import base64
import uuid
import google.auth
from google.cloud import storage, pubsub_v1
from itsdangerous import base64_decode

from . import helper

# local development only
if os.path.exists(r"..\ignore"):
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.abspath(r"..\ignore\ece528-roadside-35eaaf122e30.json")
    os.environ['GRPC_DEFAULT_SSL_ROOTS_FILE_PATH_ENV_VAR'] = r"..\ignore\ca_cert.pem"
credentials, project = google.auth.default()


app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def home():
    return render_template('home.html')

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
        helper.save_json(f'submissions\{submission_id}.json', user_info)

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
        return render_template('request_made.html', infos=user_info, user_location_url=user_location_url)

    if request.method == 'GET':
        return redirect(url_for('home'))
