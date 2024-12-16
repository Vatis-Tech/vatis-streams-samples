import json
import os
import sys
import threading
import uuid
from typing import Generator, Optional
import signal

import websocket
import pyaudio

# configuration #####
BASE_URL: str = 'wss://ws-gateway.vatis.tech'
DISPLAY_PARTIAL_FRAMES: bool = True
# configuration end #####

EOS = '{"type": "END_OF_STREAM"}'
interrupted: bool = False
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
        on_close=lambda ws, _, __: print(f'\nTranscription:\n\n{final_transcript}'),
    )

    connection.run_forever(ping_interval=5)


def on_open(ws: websocket.WebSocket, stream_generator: Generator[bytes, None, None]):
    def _send_data():
        for data in stream_generator:
            ws.send_bytes(data)

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
        print(f'{formatted_start:>6} - {formatted_end:<6} - {frame_type:<7}: {transcript}', flush=True)


def create_wav_headers(channels: int, sample_rate: int, sample_width: int) -> bytes:
    import wave
    import io

    buffer = io.BytesIO()

    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.setnframes(0)

    return buffer.getvalue()


def select_input_device(pa: pyaudio.PyAudio) -> int:
    info = pa.get_host_api_info_by_index(0)
    numdevices: int = info.get('deviceCount')

    default_input_device: Optional = pa.get_default_input_device_info()
    default_input_device_index: Optional[int] = None

    if default_input_device:
        default_input_device_index = default_input_device.get('index')

    for i in range(0, numdevices):
        if (pa.get_device_info_by_index(i).get('maxInputChannels')) > 0:
            print("Input Device index ",
                  i,
                  " - ",
                  pa.get_device_info_by_index(i).get('name'),
                  ' (default)' if i == default_input_device_index else '')

    index = input('Select input device index: ')

    if not index:
        if default_input_device_index:
            return default_input_device_index
        else:
            raise ValueError('No input device selected')
    else:
        return int(index)


def stream_microphone(p: pyaudio.PyAudio, input_device_index: int, chunk_size: int = 1024) -> Generator[bytes, None, None]:
    sample_format = pyaudio.paInt16
    channels: int = 1
    sample_rate: int = 16000
    sample_width: int = pyaudio.get_sample_size(sample_format)

    stream = p.open(format=sample_format,
                    channels=channels,
                    rate=sample_rate,
                    input=True,
                    frames_per_buffer=chunk_size,
                    input_device_index=input_device_index)

    try:
        yield create_wav_headers(channels, sample_rate, sample_width)

        print('Recording started')

        while not interrupted:
            data = stream.read(chunk_size)
            yield data

        print('Recording stopped')
    finally:
        stream.stop_stream()
        stream.close()

        p.terminate()


def signal_handler(sig, frame):
    global interrupted
    interrupted = True
    try:
        sys.exit(0)
    except SystemExit:
        pass


if __name__ == '__main__':
    api_key: str = os.environ.get('API_KEY')
    stream_configuration_template_id: str = os.environ.get('CONFIGURATION_ID', '670ba9e0efa59fe6aecd56f1')

    signal.signal(signal.SIGINT, signal_handler)

    p = pyaudio.PyAudio()

    input_device_index = select_input_device(p)

    try:
        transcribe(stream_generator=stream_microphone(p, input_device_index),
                   api_key=api_key,
                   stream_configuration_template_id=stream_configuration_template_id)
    finally:
        p.terminate()
