# UniFi Protect G6 Entry (HACS friendly)

This is a minimal Home Assistant custom integration scaffold to expose a UniFi G6 entry doorbell as a camera (RTSP) and provide a best-effort `send_audio` service for two-way audio using `ffmpeg`.

Important notes
- This is an integration scaffold. Two-way audio with UniFi Protect devices is device- and firmware-dependent. For production-grade two-way audio prefer the official UniFi Protect integration or the `pyunifiprotect` library.
- `ffmpeg` must be installed on the host for the `send_audio` service to work.

Installation via HACS
1. Add this repository as a custom repository (Integration category) in HACS.
2. Install the integration from HACS and restart Home Assistant.

## API-based Setup

This version uses the UniFi Protect API for authentication, camera discovery, and two-way audio streaming.

### Configuration Example
Add your UniFi Protect host, username, and password to `configuration.yaml`:

```yaml
unifi_protect_g6_entry:
  host: 192.168.1.100
  username: YOUR_UNIFI_USERNAME
  password: YOUR_UNIFI_PASSWORD
```

### Two-Way Audio
- The `send_audio` service streams audio to the doorbell using the UniFi Protect API's talkback WebSocket endpoint.
- Audio is encoded with ffmpeg (AAC/ADTS) and sent directly to the doorbell for real-time playback.

#### Example Service Call
```yaml
service: unifi_protect_g6_entry.send_audio
data:
  doorbell_id: <camera_id>
  audio_file: /config/www/doorbell_message.wav
```

### Requirements
- `ffmpeg` must be installed on the Home Assistant host.
- UniFi Protect must be accessible from Home Assistant.

### Limitations
- Only basic authentication and camera discovery are implemented.
- For advanced features (motion, events, video streaming), extend the integration or use the official UniFi Protect integration.
