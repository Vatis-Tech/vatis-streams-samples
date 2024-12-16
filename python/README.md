# Python

[![Python](https://img.shields.io/badge/python-3.10+-green)](https://www.python.org/downloads/)

## Environment setup

- create a virtual environment
  ```bash
    python -m venv .venv
  ```

- activate the virtual environment
  ```bash
    source .venv/bin/activate
  ```
  
- install the dependencies
  ```bash
    pip install -r requirements.txt
  ```
  
- export the `API_KEY`
  ```bash
    export API_KEY=<your api key>
  ```
  Optionally, you can explicitly specify a stream configuration template id:
  ```bash
    export CONFIGURATION_ID=<your stream template id>
  ```
 
## Use-cases

### Transcribe file
```bash
python transcribe-file.py
```

Optionally, you can specify the file path:
```bash
python transcribe-file.py <file/path>
```

### Transcribe link
```bash
python transcribe-link.py
```

Optionally, you can specify the link:
```bash
python transcribe-link.py <https://your/link>
```

### Transcribe file real-time
```bash
python transcribe-file-real-time.py
```

Optionally, you can specify the file path:
```bash
python transcribe-file-real-time.py <file/path>
```

### Transcribe microphone feed

Install the `pyaudio` library:
```bash
pip install pyaudio
```

Then run the script:
```bash
python transcribe-microphone-feed.py
```