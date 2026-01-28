# Vatis Streams API Integration Samples

[![Documentation](https://img.shields.io/badge/docs-passing-green)](https://docs.vatis.tech/introduction)
[![API Access](https://img.shields.io/badge/access-api--key-blue)](https://vatis.tech/app/playground/transcribe)

This repository contains sample code for integrating with the Vatis Streams API. Feel free to pick the language and
use-case of your choice, and create a PR with additional languages or use-cases.

## API Access

Create an account on the [Vatis Tech platform](https://vatis.tech/app) and get
your [API key](https://vatis.tech/app/playground/transcribe).

## Available examples

| Use-case                       |                  Python                   |
|:-------------------------------|:-----------------------------------------:|
| **Transcribe file**            |      [✅](python/transcribe-file.py)       |
| **Transcribe link**            |      [✅](python/transcribe-link.py)       |
| **Transcribe file real-time**  | [✅](python/transcribe-file-real-time.py)  |
| **Transcribe microphone feed** | [✅](python/transcribe-microphone-feed.py) |
| **Audio intelligence**         |     [✅](python/audio-intelligence.py)     |
| **Webhook**                    |  [✅](python/transcribe-file-webhook.py)   |
| **Transcription enhancement**  |  [✅](python/transcribe-file-enhanced.py)  |

## Microphone feed

To execute any example involving the microphone feed that does not run in the browser, follow the steps below:
- Linux
  - install the `portaudio` library
    ```bash
    sudo apt-get install portaudio19-dev
    ```
- MacOS
  - install the `portaudio` library
      ```bash
      brew install portaudio
      ```