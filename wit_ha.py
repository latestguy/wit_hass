import json
import sys
import time
import urllib.request
import webbrowser
from io import BytesIO
from threading import Thread

import cairosvg
import pyzbar.pyzbar as pyzbar
import qrcode
import requests
from flask import Flask, redirect, request
from PIL import Image
from werkzeug.serving import make_server


from train_list import FINAL_TRAIN, TRAIN_SWITCH, TRAIN_LIGHT

app = Flask(__name__)
server = None

ha_token_file = 'ha_token'
client_id = 'http://127.0.0.1:5000'
redirect_uri = 'http://127.0.0.1:5000/auth_callback'
authorization_url = 'http://localhost:8123/auth/authorize'
token_url = 'http://localhost:8123/auth/token'

refresh_token: str = None
access_token: str = None
server_thread: Thread = None


class Wit():
    "Wit api class."

    def __init__(self, token: str) -> None:
        self.__token = token

        self.__headers = {
            "Authorization": f"Bearer {self.__token}",
            "Content-Type": "application/json",
        }

    def add_intent(self, intent: str) -> bool:
        "add a intent for wit"

        intent_api = "https://api.wit.ai/intents"
        data = json.dumps({
            "name": intent,
        })

        response = requests.post(intent_api, headers=self.__headers, data=data)
        if response.status_code == 200:
            print(f"intent {intent} already registerd!")
            return True
        elif response.status_code == 400:
            if "already exists" in response.json()['error']:
                print(f"{response.json()['error']}, skip")
                return True
            else:
                print(f"{response.json()}")
                return False
        else:
            print(f"{response.json()}")
            return False

    def add_entity(self, entity_data: dict) -> bool:
        """add an entity for wit"""

        entity_url = "https://api.wit.ai/entities?v=20230310"

        # print(f'{entity_data}')

        response = requests.post(url=entity_url, headers=self.__headers, json=entity_data)
        if response.status_code == 200:
            return True
        elif response.status_code == 400:
            if "already-exists" in response.json()['code']:
                print(f"{response.json()['error']}, skip")
                return True
        else:
            print(f"{response.json()}")
            return False
        
    def add_entity_keyword(self, name: str, keyword_data: dict) -> bool:
        """add an entity for wit"""

        keyword_url = "https://api.wit.ai/entities/"+name+"/keywords"

        # print(f'{keyword_data}')

        response = requests.post(url=keyword_url, headers=self.__headers, json=keyword_data)
        # print(f"resp: {response.text}")
        if response.status_code == 200:
            return True
        elif response.status_code == 400:
            if "already exists" in response.json()['error']:
                print(f"{response.json()['error']}, skip")
                return True
        else:
            print(f"{response.json()}")
            return False

    def add_trait(self, trait: str) -> bool:
        """add a trait for wit."""
        
        trait_url = "https://api.wit.ai/traits"

        data = {
            "name": trait,
            "values": ["on", "off"]
        }

        response = requests.post(url=trait_url, headers=self.__headers, json=data)
        if response.status_code == 200:
            print(f"{trait} register success!")
            return True
        elif response.status_code == 400:
            if "already-exists" in response.json()['code']:
                print(f"{response.json()['error']}, skip")
                return True
        else:
            print(f"{response.json()}")
            return False


    def add_utterance(self, utterance: dict):
        """add an utterance for wit."""

        ut_url = "https://api.wit.ai/utterances"
        data = json.dumps(utterance)

        response = requests.post(url=ut_url, headers=self.__headers, data=data)
        if response.status_code == 200:
            print(f"\"{utterance[0]['text']}\" register success!")
            return True
        elif response.status_code == 400:
            if "already-exists" in response.json()['code']:
                print(f"utterance: {response.json()['error']}, skip")
                return True
        else:
            print(f"{response.json()}")
            return False

    def pack_utterance_data(self, name: str, type: str, prefix: str):
        """pack utterance data for self.add_utterance"""

        # name = 'hello 3'
        # type = 'switch'
        text = f"{prefix} {name} {type}"
        body = f"{type}.{name}".replace(' ', '_')
        print(f'train text: {text}')
        # print(f'body: {body}')
        ut_1: list = [{
            "text": text,
            "intent": "on_off",
            "entities": [
                {
                    "entity": "ha_dev:ha_dev",  # map for entity Role in wit web
                    "start": text.index(name),
                    "end": text.index(name) + len(name),
                    "body": body,               # map for entity Resolved value in wit web
                    "entities": []
                },
                {
                    "entity": "ha_type:ha_type",
                    "start": text.index(type),
                    "end": text.index(type) + len(type),
                    "body": type,
                    "entities": []
                }
            ],
            "traits": [
                {
                    "trait": "wit$on_off",
                    "value": "off"
                }
            ]
        }]

        return ut_1
    
    def message(self, user_input: str) -> dict:
        """handle the utterance which user input."""
        # eg. Turn off hello 1 switch
        ut_url = "https://api.wit.ai/message"
        params = {
            'q': user_input,
        }

        response = requests.get(url=ut_url, headers=self.__headers, params=params)
        # print(f'response: {response.text}')
        if response.status_code == 200:
            return response.json()


@app.route('/')
def index():
    authorize_url = f'{authorization_url}?client_id={client_id}&redirect_uri={redirect_uri}'
    return redirect(authorize_url)
    # return f'<a href="{authorize_url}">点击授权</a>' 

@app.route('/auth_callback')
def auth_callback():
    global refresh_token
    global access_token
    code = request.args.get('code')
    response = requests.post(token_url, data={
        'grant_type': 'authorization_code', 
        'code': code,
        'client_id': client_id,
    })
    print(f'{response.text}')
    access_token = response.json()['access_token']
    refresh_token = response.json()['refresh_token']
    with open(ha_token_file, "w") as f:
        tk_data = {
            "access_token": access_token,
            "refresh_token": refresh_token
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
    """Check homeassistant refresh token if valid."""

    global access_token

    try:
        with open(ha_token_file, "r") as f:
            data = json.load(f)
            access_token = data["access_token"]
            # print(f'token: {data}')
    except FileNotFoundError as err:
        print(f'open {ha_token_file} failed! start go to web auth')
        return False

    if access_token is not None:
        api_url = 'http://localhost:8123/api/'
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        resp = requests.get(url=api_url, headers=headers)
        if resp.status_code == 200:
            # refresh token is valid
            print(f'refresh token is valid')
            return True
        else:
            # refresh token is invalid, need to regenerator
            print(f'refresh token is Invalid')
            # print(f'{resp.status_code, resp.text}')
            return False
    else:
        print(f"have no refresh token!")
        return False

def start_ha_server():
    '''Create and start flask web for homeassistant auth.'''

    global server
    print(f'* Running on http://127.0.0.1:5000')
    server = make_server('127.0.0.1', 5000, app)
    server.timeout = 1
    server.serve_forever()

def ha_2_wit_train(wit: Wit, ha_data: dict = None, train_data: dict = None) -> bool:
    """Train wit utterance with homeassistant entity id and type."""

    if not ha_data:
        return False
    if not train_data:
        return False

    # for type in ha_data:
    #     print(f"type: {type}")
    # for list in train_data:
    #     print(f"{list}")

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
        "Authorization": f"Bearer {access_token}",
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
        print(f"response is None")
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
        print(f'{entity_id}')

        serv_api_base = f'http://localhost:8123/api/services/'
        data = {
            "entity_id": entity_id
        }
        print(f'access_token = {access_token}')
        headers = {
            "Authorization": f"Bearer {access_token}",
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
        