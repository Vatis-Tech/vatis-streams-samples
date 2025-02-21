import json
import os
import sys
import threading
import uuid
from pathlib import Path
from time import sleep
from typing import List

import requests

# configuration #####
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
        'patches': {
            'ask0': 'Identify all the issues raised in this conversations and whether it was solved or not.',
            'ask0Id': 'client_issues',
            'ask0Format': json.dumps(ResponseSchema.model_json_schema())
        }
    }

    return json.dumps(message)


def transcribe(file_path: Path, api_key: str, stream_configuration_template_id: str):
    assert api_key, 'API_KEY is required'

    stream_id: str = str(uuid.uuid4())

    # Upload the file
    upload_url: str = 'https://http-gateway.vatis.tech/http-gateway/api/v1/upload'

    query_parameters: dict = {
        'streamConfigurationTemplateId': stream_configuration_template_id,
        'id': stream_id,
        'persist': 'true'
    }

    upload_headers: dict = {
        'Accept': 'application/json',
        'Authorization': f'Basic {api_key}'
    }

    with open(file_path, 'rb') as payload:
        # (part_name, (filename, fileobj, content_type))
        multipart = (
            ('config', (None, _ask_anything_configuration(), 'application/json')),
            ('file', (None, payload, 'application/octet-stream'))
        )

        upload_response = requests.post(upload_url, headers=upload_headers, params=query_parameters, files=multipart)

    if not upload_response.ok:
        print(f'Error on file upload: {upload_response.status_code} - {upload_response.json()}')
        return

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


if __name__ == '__main__':
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = os.environ.get('FILE_PATH', '../data/stt/test-phone-call.wav')

    file_path = Path(file_path).resolve()

    assert file_path.exists() and file_path.is_file(), f'File {file_path} does not exist or is not a file'

    api_key: str = os.environ.get('API_KEY')
    stream_configuration_template_id: str = os.environ.get('CONFIGURATION_ID', '668115d123bca7e3509723d4')

    transcribe(file_path=file_path,
               api_key=api_key,
               stream_configuration_template_id=stream_configuration_template_id)
