import json
import os
import sys
import threading
import uuid
from pathlib import Path
from time import sleep
from typing import Generator, List

import requests
import websocket

# configuration #####
BASE_URL: str = 'wss://ws-gateway.vatis.tech'
DISPLAY_PARTIAL_FRAMES: bool = False
# configuration end #####

EOS = '{"type": "END_OF_STREAM"}'
closed_event: threading.Event = threading.Event()


def _ask_anything_configuration() -> str:
    from pydantic import BaseModel, Field

    class ClientIssue(BaseModel):
        issue: str = Field()
        solved: bool = Field()

    class ResponseSchema(BaseModel):
        issues: List[ClientIssue] = Field()

    message: dict = {
        'type': 'CONFIGURATION',
        'patches': {
            'ask0': 'Identify all the issues raised in this conversations and whether it was solved or not.',
            'ask0Id': 'client_issues',
            'ask0Format': json.dumps(ResponseSchema.model_json_schema())
        }
    }

    return json.dumps(message)


def transcribe(stream_generator: Generator[bytes, None, None], api_key: str, stream_configuration_template_id: str):
    assert api_key, 'API_KEY is required'

    stream_id: str = str(uuid.uuid4())

    # configuration options here
    parameters = {
        'id': stream_id,
        'streamConfigurationTemplateId': stream_configuration_template_id,
        'language': 'en',  # set the language here
        'configurationMessage': 'true',  # indicate a configuration message will be sent
        'egress': 'false',  # do not send responses on the websocket, the final result will be exported at the end
    }

    # authentication headers
    headers = {
        'Authorization': f'Basic {api_key}',
    }

    # define the upload connection
    connection: websocket.WebSocket = websocket.create_connection(
        f'{BASE_URL}/ws-gateway/api/v1/?{"&".join([f"{k}={v}" for k, v in parameters.items()])}',
        header=headers,
        enable_multithread=False,
    )

    connection.send_text(_ask_anything_configuration())

    for data in stream_generator:
        connection.send_bytes(data)

    upload_response: dict = json.loads(connection.recv())
    connection.close()

    if upload_response['type'] == 'ERROR':
        raise RuntimeError(f'upload error: {upload_response}')

    print(f'File uploaded successfully: {stream_id}')

    # wait on stream status
    status_url = f'https://stream-service.vatis.tech/stream-service/api/v1/streams/{stream_id}'

    status_headers = {
        'Accept': 'application/json',
        'Authorization': f'Basic {api_key}',
    }

    while True:
        status_response = requests.request('GET', status_url, headers=status_headers)

        if not status_response.ok:
            print(f'Error on stream status: {status_response.json()}')
            return

        if status_response.json()['state'] == 'COMPLETED':
            break
        elif status_response.json()['state'] == 'FAILED':
            print(f'Error on stream: {status_response.json()}')
            break
        else:
            sleep(3)
            print(f'Waiting for stream to be completed: {stream_id}')

    print(f'The stream is completed: {stream_id}')

    # Export the results
    export_url: str = f"https://export-service.vatis.tech/export-service/api/v1/export/JSON?streams={stream_id}"

    export_headers: dict = {
        'Authorization': f'Basic {api_key}',
        'Accept': 'application/json'
    }

    export_response = requests.request('GET', export_url, headers=export_headers)
    export_result = export_response.json()

    if export_response.ok:
        print(json.dumps(export_result, indent=2))
    else:
        print(f'Error on export: {export_result}')


def stream_file(file_path: Path, chunk_size: int = 10*1024) -> Generator[bytes, None, None]:
    with open(file_path, 'rb') as file:
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            yield chunk


if __name__ == '__main__':
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = os.environ.get('FILE_PATH', '../data/stt/test-phone-call.wav')

    file_path = Path(file_path).resolve()

    assert file_path.exists() and file_path.is_file(), f'File {file_path} does not exist or is not a file'

    api_key: str = os.environ.get('API_KEY')
    stream_configuration_template_id: str = os.environ.get('CONFIGURATION_ID', '668115d123bca7e3509723d4')

    transcribe(stream_generator=stream_file(file_path),
               api_key=api_key,
               stream_configuration_template_id=stream_configuration_template_id)
