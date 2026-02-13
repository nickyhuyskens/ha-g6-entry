"""UniFi Protect G6 Entry integration (HACS root-level).

This integration provides a camera entity that exposes an RTSP stream
and a best-effort `send_audio` service for two-way audio using `ffmpeg`.
"""
import asyncio
import logging
import shutil
import subprocess
import aiohttp

from homeassistant.const import CONF_HOST
from homeassistant.helpers import discovery

from const import DOMAIN, DEFAULT_NAME
from unifi_protect_api import UniFiProtectClient

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    conf = config.get(DOMAIN, {})
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["config"] = conf

    # Authenticate and discover cameras using UniFi Protect API
    host = conf.get("host")
    username = conf.get("username")
    password = conf.get("password")
    if not (host and username and password):
        _LOGGER.error("UniFi Protect host, username, and password must be set in config")
        return False

    api_client = UniFiProtectClient(host, username, password)
    success = await api_client.authenticate()
    if not success:
        _LOGGER.error("Failed to authenticate with UniFi Protect API")
        return False

    cameras = await api_client.get_cameras()
    hass.data[DOMAIN]["api_client"] = api_client
    hass.data[DOMAIN]["cameras"] = cameras

    # Forward to camera platform loader
    hass.async_create_task(
        discovery.async_load_platform(hass, "camera", DOMAIN, {}, config)
    )

    # Register a service to send audio to the doorbell (API-based)
    async def async_send_audio_service(call):
        hass.loop.create_task(_handle_send_audio(hass, call.data))

    hass.services.async_register(DOMAIN, "send_audio", async_send_audio_service)

    return True

async def _handle_send_audio(hass, data):
    audio_file = data.get("audio_file")
    entity_id = data.get("entity_id")
    doorbell_id = data.get("doorbell_id")

    if not audio_file:
        _LOGGER.error("send_audio requires 'audio_file' (local path)")
        return

    api_client = hass.data[DOMAIN].get("api_client")
    cameras = hass.data[DOMAIN].get("cameras", [])

    # Find camera by entity_id or doorbell_id
    camera = None
    if doorbell_id:
        camera = next((c for c in cameras if c.get("id") == doorbell_id), None)
    elif entity_id:
        state = hass.states.get(entity_id)
        if state:
            cam_name = state.attributes.get("friendly_name")
            camera = next((c for c in cameras if c.get("name") == cam_name), None)
    if not camera and cameras:
        camera = cameras[0]

    if not camera:
        _LOGGER.error("No camera found for send_audio")
        return

    camera_id = camera.get("id")
    talkback_url = await api_client.get_talkback_url(camera_id)
    if not talkback_url:
        _LOGGER.error("No talkback URL found for camera %s", camera_id)
        return

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        _LOGGER.error("ffmpeg not found on system PATH; install ffmpeg to use send_audio")
        return

    # Use ffmpeg to encode audio and stream to WebSocket
    cmd = [
        ffmpeg,
        "-re",
        "-i",
        audio_file,
        "-acodec",
        "aac",
        "-f",
        "adts",
        "-muxdelay",
        "0",
        "-flags",
        "low_delay",
        "-fflags",
        "nobuffer",
        "-hide_banner",
        "-loglevel",
        "error",
        "-",
    ]

    _LOGGER.info("Starting ffmpeg to stream %s -> %s", audio_file, talkback_url)

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(talkback_url, ssl=False) as ws:
                while True:
                    chunk = await process.stdout.read(4096)
                    if not chunk:
                        break
                    await ws.send_bytes(chunk)
                await ws.close()
        await process.wait()
        stderr = await process.stderr.read()
        if process.returncode != 0:
            _LOGGER.error("ffmpeg failed (%s): %s", process.returncode, stderr.decode(errors="ignore"))
        else:
            _LOGGER.debug("ffmpeg finished streaming audio")
    except Exception as exc:
        _LOGGER.exception("Error streaming audio to talkback: %s", exc)
