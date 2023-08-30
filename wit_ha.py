import json
import sys
import time
import urllib.request
import webbrowser
from io import BytesIO
from threading import Thread
from websockets.sync.client import connect

import cairosvg
import pyzbar.pyzbar as pyzbar
import qrcode
import requests
from flask import Flask, redirect, request
from PIL import Image
from werkzeug.serving import make_server


from train_list import FINAL_TRAIN, TRAIN_SWITCH, TRAIN_LIGHT
from wit import Wit

app = Flask(__name__)
server = None

ha_token_file = 'ha_token'
client_id = 'http://127.0.0.1:5000'
redirect_uri = 'http://127.0.0.1:5000/auth_callback'
authorization_url = 'http://localhost:8123/auth/authorize'
token_url = 'http://localhost:8123/auth/token'

refresh_token: str = None
access_token: str = None
lla_token: str = None
server_thread: Thread = None

@app.route('/')
def index():
    authorize_url = f'{authorization_url}?client_id={client_id}&redirect_uri={redirect_uri}'
    return redirect(authorize_url)
    # return f'<a href="{authorize_url}">点击授权</a>' 

@app.route('/auth_callback')
def auth_callback():
    global refresh_token
    global access_token
    global lla_token
    code = request.args.get('code')
    response = requests.post(token_url, data={
        'grant_type': 'authorization_code', 
        'code': code,
        'client_id': client_id,
    })
    print(f'{response.text}')
    access_token = response.json()['access_token']
    refresh_token = response.json()['refresh_token']
    lla_token = gen_lla_token()
    with open(ha_token_file, "w") as f:
        tk_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "lla_token": lla_token
        }
        json.dump(tk_data, f)

    # 使用access_token访问资源...
    # return '授权完成'
    return """授权完成
    <script>
      // 等待2秒后关闭页面
      setTimeout(function() {
        window.location.replace('about:blank');
      }, 2000);
    </script>
    """

def check_ha_token() -> bool:
    """Check homeassistant lla and access token if valid."""

    global access_token, lla_token

    try:
        with open(ha_token_file, "r") as f:
            data = json.load(f)
            access_token = data.get("access_token", None)
            lla_token = data.get("lla_token", None)
    except json.decoder.JSONDecodeError as err:
        print(f"parse ha_token json data failed! start go to web auth")
        return False
    except FileNotFoundError as err:
        print(f'open {ha_token_file} failed! start go to web auth')
        return False

    if lla_token is not None:
        token = lla_token
    elif access_token is not None:
        token = access_token
    else:
        print(f"have no lla and access token!")
        return False

    api_url = 'http://localhost:8123/api/'
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    resp = requests.get(url=api_url, headers=headers)
    if resp.status_code == 200:
        # token is valid
        print(f'token is valid')
        return True
    else:
        # token is invalid, need to regenerator
        print(f'token is Invalid')
        # print(f'{resp.status_code, resp.text}')
        return False

def gen_lla_token() -> str:
    global access_token

    # 1.Client connects
    with connect("ws://localhost:8123/api/websocket") as websocket:
        resp = websocket.recv()
        # # 2.Authentication phase
        if "auth_required" != json.loads(resp).get("type", None):
            print(f"Ha ws msg have no \"auth_required\"!")
            return None

        # 2.1 sends auth message
        auth_msg = json.dumps({
            "type": "auth",
            "access_token": access_token
        })
        websocket.send(auth_msg)
        resp = websocket.recv()
        if "auth_ok" != json.loads(resp).get("type", None):
            print(f"Ha ws msg have no \"auth_ok\"!")
            return None
        print(f"ha resp auth status: {resp}")

        lla_msg = json.dumps({
            "id": 11,
            "type": "auth/long_lived_access_token",
            "client_name": "Loona",
            # "client_icon": null,
            "lifespan": 365
        })
        websocket.send(lla_msg)
        resp = websocket.recv()
        if json.loads(resp).get("success", False) is True:
            print(f"True ha resp lla token: {resp}")
            return json.loads(resp).get("result")
        else:
            print(f"Ha ws generate Long-Lived Access Token failed!")
            return None


def start_ha_server():
    '''Create and start flask web for homeassistant auth.'''

    global server
    print(f'* Running on http://127.0.0.1:5000')
    server = make_server('127.0.0.1', 5000, app)
    server.timeout = 1
    server.serve_forever()

def ha_2_wit_train(wit: Wit, ha_data: dict = None, train_data: dict = None) -> bool:
    """Train wit utterance with homeassistant entity id and type."""

    if ha_data is None or train_data is None:
        return False

    """1. add intent on_off for switch dev type """
    print(f"==========Add Intent==========")
    wit.add_intent("on_off")

    # """2. add entity"""
    print(f"==========Add Entity (ha_dev)==========")
    entity_data = {
        "name": "ha_dev",
        "roles": ["ha_dev"],
        "lookups": ["keywords"]
    }
    wit.add_entity(entity_data)

    print(f"==========Add Keyword==========")
    # add keyword and synonyms
    for type in ha_data:
        for entity in ha_data[type]:
            try:
                entity_data = {
                    "keyword": entity["entity_id"],    # unique_id for hass
                    "synonyms": [entity["entity_id"]], # unique_id for hass
                }
            except:
                print(f'add_entity err!')
                continue
            if wit.add_entity_keyword("ha_dev", entity_data):
                print(f"eneity add keyword: {entity['entity_id']} success!")

    print(f"==========Add Entity (ha_type)==========")
    ha_type = {
        "name": "ha_type",
        "roles": [],
    }
    wit.add_entity(ha_type)

    print(f"==========Add Trait==========")
    # """3. add trait"""
    wit.add_trait("wit$on_off")

    print(f"==========Add Utterance==========")
    for type in ha_data:
        print(f'+++type: {type}')
        if type not in FINAL_TRAIN:
            continue
        for train in FINAL_TRAIN[type]:
            for entity in ha_data[type]:
                # print(f"name: {entity['entity_id']}, type: {type}, prefix: {train}")
                ut_data = wit.pack_utterance_data(name=entity["name"], type=type, prefix=train)
                if not wit.add_utterance(ut_data):
                    continue

def loona_paring_qr() -> bool:
    """Decode loona paring qr code."""
    api_url = 'http://localhost:8123/api/loona/pairingqr'
    headers = {
        "Authorization": f"Bearer {lla_token}",
        "Content-Type": "image/svg+xml"
    }
    req = urllib.request.Request(api_url, headers=headers)
    try:
        resp = urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        print(f'error code: {e}')
        return None

    # 将SVG格式的图像转换为PIL Image对象
    try: 
        svg_data = resp.read().decode()
        png_data = cairosvg.svg2png(bytestring=svg_data)
        image = Image.open(BytesIO(png_data))
    except urllib.error.URLError as e:
        print(f"qrcode response is None, please add eneities in Loona intergration first!")
        return None

    # 解析二维码中的数据
    decoded_data = pyzbar.decode(image)
    if len(decoded_data) == 0:
        raise ValueError("No QR codes found")
    elif len(decoded_data) > 1:
        raise ValueError("Multiple QR codes found")
    else:
        qr_code = decoded_data[0].data.decode("utf-8")
        print("QR code:", qr_code)
    return qr_code


def do_control(wit_resp: dict):
    print(f'{wit_resp}')
    if wit_resp is not None and wit_resp["entities"]["ha_dev:ha_dev"] is not None:
        entity: list = wit_resp["entities"]["ha_dev:ha_dev"]
        trait: dict = wit_resp["traits"]["wit$on_off"][0]
        entity_id: str = entity[0]["value"]
        action: str = trait["value"]
        type: str = wit_resp["entities"]["ha_type:ha_type"][0]["body"]
        print(f'to control entity_id: {entity_id}')

        serv_api_base = f'http://localhost:8123/api/services/'
        data = {
            "entity_id": entity_id
        }
        headers = {
            "Authorization": f"Bearer {lla_token}",
            "Content-Type": "application/json"
        }
        if action in "turn_on":
            serv_api = serv_api_base + type + "/turn_on"
        if action in "turn_off":
            serv_api = serv_api_base + type + "/turn_off"
        print(f'serv_api: {serv_api}')
        response = requests.post(url=serv_api, headers=headers, json=data)
        print(f"{response.text}")

if __name__ == '__main__':
    print(f'hello world!')

    if not check_ha_token():
        # token is invalid, open web tab to login
        server_thread = Thread(target=start_ha_server)
        server_thread.start()
        webbrowser.open('http://127.0.0.1:5000', new=2)

        while True:
            if check_ha_token():
                print(f'get refresh token success!')
                # server.shutdown()
                break
            else:
                print('...', end='')
                time.sleep(3)

    print(f'===================Welcome to Loona.===================')

    qr_code = loona_paring_qr()
    if not qr_code:
        print(f"Have no QR Code in homeassistant!")
        exit(1)

    print(f"train list: {TRAIN_SWITCH}")

    wit = Wit("3NXAXAJKKJDWNKPA4N7CN25E6ZCPCIUS")

    if ha_2_wit_train(wit, ha_data=json.loads(qr_code).get("type", None), train_data=FINAL_TRAIN) is False:
        print(f"No ha_data or train_list!!")
        exit(0)

    # Start conversation
    while True:
        try:
            resp = wit.message(input("Enter your command:"))
            # resp = json.loads(resp)
            do_control(resp)

        except KeyboardInterrupt:
            # print(f"Unexpected error: {sys.exc_info()[0]}")
            print(f"Abort by user.")
            exit(0)
        else:
            pass
        