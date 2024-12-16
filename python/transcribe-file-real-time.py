import json
import os
import sys
import threading
import uuid
from pathlib import Path
from typing import Generator

import websocket

# configuration #####
BASE_URL: str = 'wss://ws-gateway.vatis.tech'
DISPLAY_PARTIAL_FRAMES: bool = False
# configuration end #####

EOS = '{"type": "END_OF_STREAM"}'
closed_event: threading.Event = threading.Event()
final_transcript: str = ''


def transcribe(stream_generator: Generator[bytes, None, None], api_key: str, stream_configuration_template_id: str):
    assert api_key, 'API_KEY is required'

    stream_id: str = str(uuid.uuid4())

    # configuration options here
    parameters = {
        'id': stream_id,
        'streamConfigurationTemplateId': stream_configuration_template_id,
        'language': 'en',  # set the language here
    }

    # authentication headers
    headers = {
        'Authorization': f'Basic {api_key}',
    }

    # define the connection and its callbacks
    connection: websocket.WebSocketApp = websocket.WebSocketApp(
        f'{BASE_URL}/ws-gateway/api/v1/?{"&".join([f"{k}={v}" for k, v in parameters.items()])}',
        header=headers,
        on_open=lambda ws: on_open(ws, stream_generator),
        on_message=on_message,
        on_error=lambda ws, error: print(f'Error: {error}'),
        on_close=lambda ws, _, __: closed_event.set(),
    )

    connection.run_forever(ping_interval=5)

    print(f'\nTranscription:\n\n{final_transcript}')


def on_open(ws: websocket.WebSocketApp, stream_generator: Generator[bytes, None, None]):
    def _send_data():
        for data in stream_generator:
            if closed_event.is_set():
                break
            ws.send_bytes(data)

        if not closed_event.is_set():
            ws.send_text(EOS)

    threading.Thread(target=_send_data, name='data-sender', daemon=True).start()


def on_message(ws: websocket.WebSocket, event_json: str):
    if not event_json:
        return

    event: dict = json.loads(event_json)

    if event['type'] == 'RESPONSE':
        try:
            print_transcription(event['response'], display_all=DISPLAY_PARTIAL_FRAMES)
        except Exception as e:
            print(f'Error processing response: {e}')
    elif event['type'] == 'ERROR':
        print(f'Error: {event["error"]}')
    elif event['type'] == 'STREAM_METADATA':
        print(f'Stream id: {event["stream"]["streamId"]}\n')
    elif event['type'] == 'END_OF_STREAM':
        ws.close()
    else:
        print(f'Unknown event: {event}')


def print_transcription(event: dict, display_all: bool = False):
    global final_transcript

    assert event['payloadSchema'] == 'tech.vatis.schema.stream.processor.messages.transcription.TranscriptionResponseDto', f'Not a transcription event: {event}'

    # filter out partial frames, display only the final results
    if event['frameType'] == 'final' or display_all:
        transcript: str = event['payload']['transcription']
        start_time: int = event['payload']['start'] / 1000
        end_time: int = event['payload']['end'] / 1000
        frame_type: str = event['frameType']

        if frame_type == 'final':
            final_transcript += transcript

        formatted_start: str = f'{start_time:.2f}'
        formatted_end: str = f'{end_time:.2f}'
        print(f'{formatted_start:>6} - {formatted_end:<6} - {frame_type:<7}: {transcript}')


def stream_file(file_path: Path, chunk_size: int = 1024) -> Generator[bytes, None, None]:
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
    stream_configuration_template_id: str = os.environ.get('CONFIGURATION_ID', '670ba9e0efa59fe6aecd56f1')

    transcribe(stream_generator=stream_file(file_path),
               api_key=api_key,
               stream_configuration_template_id=stream_configuration_template_id)