import json
import os
import threading
import uuid
from argparse import ArgumentParser
from pathlib import Path
from typing import Union

from http.server import BaseHTTPRequestHandler, HTTPServer

import requests


def transcribe(file_path: Union[str, Path],
               api_key: str,
               stream_configuration_template_id: str,
               webhook_base_url: str):
    assert api_key, 'API_KEY is required'

    stream_id: str = str(uuid.uuid4())

    # Upload the file
    upload_url: str = 'https://http-gateway.vatis.tech/http-gateway/api/v1/upload'

    query_parameters: dict = {
        'streamConfigurationTemplateId': stream_configuration_template_id,
        'id': stream_id,
        'persist': 'true',
        'webhook.stream.failed': f'{webhook_base_url}/vatis-callback/',    # callback URL for streams that enter the FAILED state
        'webhook.stream.completed': f'{webhook_base_url}/vatis-callback/', # callback URL for streams that enter the COMPLETED state
    }

    upload_headers: dict = {
        'Accept': 'application/json',
        'Authorization': f'Basic {api_key}',
        'Content-Type': 'application/octet-stream'
    }

    with open(file_path, 'rb') as payload:
        upload_response = requests.post(upload_url, headers=upload_headers, params=query_parameters, data=payload)

    if not upload_response.ok:
        print(f'Error on file upload: {upload_response.status_code} - {upload_response.json()}')
        raise Exception(f'Error on file upload: {upload_response.status_code} - {upload_response.json()}')

    print(f'File uploaded successfully: {stream_id}')


def do_on_stream_completed(stream_id: str, api_key: str):
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


def do_on_stream_failed(stream_id: str, api_key: str):
    print(f'Stream {stream_id} failed')


class WebhookCallbackHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.api_key: str = os.environ.get('API_KEY')
        super().__init__(*args, **kwargs)

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        print(f'Received webhook: {post_data.decode()}')

        webhook_data = json.loads(post_data)

        stream_id: str = webhook_data['payload']['streamId']
        state: str = webhook_data['payload']['state']

        # process the stream event
        if state == 'COMPLETED':
            do_on_stream_completed(stream_id, self.api_key)
        elif state == 'FAILED':
            do_on_stream_failed(stream_id, self.api_key)

        self.send_response(200)
        self.end_headers()

        threading.Thread(target=self.server.shutdown).start()


if __name__ == '__main__':
    parser = ArgumentParser(description='Transcribe an audio file using the Vatis API')
    parser.add_argument('--file-path', type=str, default='../data/stt/test-phone-call.wav', help='Path to the audio file to transcribe')
    parser.add_argument('--webhook-base-url', '-u', type=str, required=True, help='The base URL in the form of "<protocol>://<host>:<port>" used in the webhook URLs')
    parser.add_argument('--port', '-p', type=int, default=8081, help='Port to listen to the webhooks')
    args = parser.parse_args()

    file_path = Path(args.file_path).resolve()

    assert file_path.exists() and file_path.is_file(), f'File {file_path} does not exist or is not a file'

    api_key: str = os.environ.get('API_KEY')
    stream_configuration_template_id: str = os.environ.get('CONFIGURATION_ID', '668115d123bca7e3509723d4')

    # Start the transcription process
    transcribe(file_path=file_path,
               api_key=api_key,
               stream_configuration_template_id=stream_configuration_template_id,
               webhook_base_url=args.webhook_base_url)

    # Start the webhook listener server
    with HTTPServer(('', args.port), WebhookCallbackHandler) as httpd:
        print(f'Listening on port {args.port} for the webhook event. Press Ctrl+C to stop.')
        httpd.serve_forever()
