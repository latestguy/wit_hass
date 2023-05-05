import json
import requests

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
