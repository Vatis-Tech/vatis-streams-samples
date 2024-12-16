import uuid
from time import sleep

import requests
import os
import sys
from pathlib import Path


def transcribe(file_link: str, api_key: str, stream_configuration_template_id: str):
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
        'Authorization': f'Basic {api_key}',
        'Content-Type': 'application/octet-stream'
    }

    upload_response = requests.post(upload_url,
                                    headers=upload_headers,
                                    params=query_parameters,
                                    data=file_link.encode('utf-8'))

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
        print(export_result)
    else:
        print(f'Error on export: {export_result}')


if __name__ == '__main__':
    file_link: str

    if len(sys.argv) > 1:
        file_link = sys.argv[1]
    else:
        file_link = os.environ.get('FILE_LINK', 'https://storage.googleapis.com/vatis-tech-public-files/github/vatis-streams-samples/stt/test-phone-call.wav')

    api_key: str = os.environ.get('API_KEY')
    stream_configuration_template_id: str = os.environ.get('CONFIGURATION_ID', '668115d123bca7e3509723d4')

    transcribe(file_link=file_link,
               api_key=api_key,
               stream_configuration_template_id=stream_configuration_template_id)
