#!/usr/bin/env python3

from wit import Wit
import json

wit_token = "3NXAXAJKKJDWNKPA4N7CN25E6ZCPCIUS"

if __name__ == "__main__":
    client = Wit(wit_token)
    # response = client.message('turn off hello 1 swtich')
    # response = client.message('set bedroom light brightness to 80')
    print(f'Input your requirement: ')
    response = client.message(input())
    format_data = json.dumps(response, indent=4)
    print(f'{format_data}')
