"""
Lyra composition service.

Uses Volcengine's Music OpenAPI (GenSongForTime + QuerySong)
to generate songs remotely.

Flow:
    Composer.generate()
        -> POST GenSongForTime
        -> receive TaskID
        -> POST QuerySong until Status == 2
        -> download SongDetail.AudioUrl
        -> save to static/generated/<uuid>.mp3
        -> return a stable local audio_url for the frontend
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


logger = logging.getLogger("lyra.composition")


class CompositionError(RuntimeError):
    """Known composition-service error."""


class VolcengineSigner:
    """
    Volcengine HMAC-SHA256 signer.

    Region and Service for the music API:
        region  = cn-beijing
        service = imagination
    """

    ALGORITHM = "HMAC-SHA256"

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        region: str,
        service: str,
    ) -> None:
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.service = service

    @staticmethod
    def _sha256_hex(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _hmac_sha256(key: bytes, data: str) -> bytes:
        return hmac.new(
            key,
            data.encode("utf-8"),
            hashlib.sha256,
        ).digest()

    @staticmethod
    def _uri_encode(value: str) -> str:
        return quote(str(value), safe="-_.~")

    def sign(
        self,
        method: str,
        uri: str,
        query: dict[str, str],
        body: bytes,
        host: str,
    ) -> dict[str, str]:
        """Build the Authorization header and signed request headers."""
        now = datetime.now(timezone.utc)
        x_date = now.strftime("%Y%m%dT%H%M%SZ")
        short_date = now.strftime("%Y%m%d")

        payload_hash = self._sha256_hex(body)

        canonical_query = "&".join(
            f"{self._uri_encode(k)}={self._uri_encode(v)}"
            for k, v in sorted(query.items())
        )

        # IMPORTANT:
        # The values here must exactly match the actual headers sent.
        canonical_headers_map = {
            "content-type": "application/json",
            "host": host,
            "x-content-sha256": payload_hash,
            "x-date": x_date,
        }

        signed_headers = ";".join(
            sorted(canonical_headers_map)
        )

        canonical_headers = "".join(
            f"{name}:{canonical_headers_map[name]}\n"
            for name in sorted(canonical_headers_map)
        )

        canonical_request = "\n".join(
            [
                method.upper(),
                uri or "/",
                canonical_query,
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )

        credential_scope = (
            f"{short_date}/"
            f"{self.region}/"
            f"{self.service}/request"
        )

        canonical_request_hash = self._sha256_hex(
            canonical_request.encode("utf-8")
        )

        string_to_sign = "\n".join(
            [
                self.ALGORITHM,
                x_date,
                credential_scope,
                canonical_request_hash,
            ]
        )

        # Derive signing key:
        # kDate -> kRegion -> kService -> kSigning
        k_date = self._hmac_sha256(
            self.secret_key.encode("utf-8"),
            short_date,
        )
        k_region = self._hmac_sha256(
            k_date,
            self.region,
        )
        k_service = self._hmac_sha256(
            k_region,
            self.service,
        )
        k_signing = self._hmac_sha256(
            k_service,
            "request",
        )

        signature = hmac.new(
            k_signing,
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        authorization = (
            f"{self.ALGORITHM} "
            f"Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        return {
            "Host": host,
            "Content-Type": "application/json",
            "X-Date": x_date,
            "X-Content-Sha256": payload_hash,
            "Authorization": authorization,
        }


class Composer:
    """Generate songs through the remote Volcengine Music OpenAPI."""

    def __init__(self) -> None:
        self.host = os.getenv(
            "VOLC_HOST",
            "open.volcengineapi.com",
        )
        self.region = os.getenv(
            "VOLC_REGION",
            "cn-beijing",
        )
        self.service = os.getenv(
            "VOLC_SERVICE",
            "imagination",
        )

        # You said the account is postpaid.
        self.song_action = os.getenv(
            "VOLC_SONG_ACTION",
            "GenSongForTime",
        )
        self.api_version = os.getenv(
            "VOLC_SONG_VERSION",
            "2024-08-12",
        )
        self.model_version = os.getenv(
            "VOLC_MODEL_VERSION",
            "v4.3",
        )

        self.poll_interval = float(
            os.getenv(
                "VOLC_POLL_INTERVAL",
                "2",
            )
        )
        self.task_timeout = float(
            os.getenv(
                "VOLC_TASK_TIMEOUT",
                "240",
            )
        )

        # Resolve paths relative to project root when possible.
        default_generated_dir = (
            Path(__file__).resolve().parents[2]
            / "static"
            / "generated"
        )
        self.generated_dir = Path(
            os.getenv(
                "LYRA_GENERATED_DIR",
                str(default_generated_dir),
            )
        )

        self.access_key = os.getenv(
            "VOLC_ACCESS_KEY_ID",
            "",
        ).strip()
        self.secret_key = os.getenv(
            "VOLC_SECRET_ACCESS_KEY",
            "",
        ).strip()

        if not self.access_key:
            raise CompositionError(
                "VOLC_ACCESS_KEY_ID is not configured."
            )

        if not self.secret_key:
            raise CompositionError(
                "VOLC_SECRET_ACCESS_KEY is not configured."
            )

        self.signer = VolcengineSigner(
            access_key=self.access_key,
            secret_key=self.secret_key,
            region=self.region,
            service=self.service,
        )

        self.session = requests.Session()

        logger.info(
            "Composer ready: host=%s action=%s model=%s",
            self.host,
            self.song_action,
            self.model_version,
        )

    def generate(
        self,
        prompt: str,
        duration: int = 60,
        style: str = "",
        tempo: int = 0,
        key: str = "",
    ) -> dict[str, Any]:
        """
        Generate an original song.

        Returns:
            {
                "audio_url": "/static/generated/<uuid>.mp3",
                "duration": <actual duration in seconds>
            }
        """
        prompt = (prompt or "").strip()
        style = (style or "").strip()
        key = (key or "").strip()

        if not prompt:
            raise CompositionError(
                "Composition prompt cannot be empty."
            )

        if not 30 <= duration <= 240:
            raise CompositionError(
                "Duration must be between 30 and 240 seconds."
            )

        if tempo and not 20 <= tempo <= 300:
            raise CompositionError(
                "Tempo must be between 20 and 300 BPM."
            )

        body = self._build_generation_body(
            prompt=prompt,
            duration=duration,
            style=style,
            tempo=tempo,
            key=key,
        )

        logger.info(
            "Submitting song generation task: "
            "duration=%s, style=%r, tempo=%r, key=%r",
            duration,
            style,
            tempo,
            key,
        )

        response = self._request(
            action=self.song_action,
            body=body,
        )

        if response.get("Code") != 0:
            raise CompositionError(
                f"GenSong failed: "
                f"{response.get('Message') or response}"
            )

        result = response.get("Result") or {}
        task_id = result.get("TaskID")

        if not task_id:
            raise CompositionError(
                f"GenSong response did not contain TaskID: {response}"
            )

        logger.info(
            "Song generation task created: %s",
            task_id,
        )

        song_detail = self._wait_for_song(task_id)

        remote_audio_url = str(
            song_detail.get("AudioUrl") or ""
        ).strip()

        if not remote_audio_url:
            raise CompositionError(
                "Song generation succeeded but AudioUrl is empty."
            )

        local_audio_url = self._download_audio(
            remote_audio_url,
        )

        actual_duration = duration
        raw_duration = song_detail.get("Duration")

        if raw_duration is not None:
            try:
                actual_duration = int(round(float(raw_duration)))
            except (TypeError, ValueError):
                logger.warning(
                    "Could not parse returned duration: %r",
                    raw_duration,
                )

        return {
            "audio_url": local_audio_url,
            "duration": actual_duration,
        }

    def _build_generation_body(
        self,
        prompt: str,
        duration: int,
        style: str,
        tempo: int,
        key: str,
    ) -> dict[str, Any]:
        """Translate Lyra's composition parameters to Volcengine fields."""
        body: dict[str, Any] = {
            "Prompt": self._build_prompt(
                prompt=prompt,
                style=style,
                tempo=tempo,
                key=key,
            ),
            "ModelVersion": self.model_version,
            "Duration": duration,
            "Lang": "Chinese",
            "VodFormat": "mp3",
        }

        # Keep optional structured fields out of the first stable path.
        # Volcengine validates Genre/Tempo/Key/Kmode against model-specific
        # vocabularies. User-facing values such as "90 BPM", "pop", or
        # "C major" are safer to express in Prompt unless they are known
        # to match the exact v4.3 enum vocabulary.
        return body

    @staticmethod
    def _build_prompt(
        prompt: str,
        style: str,
        tempo: int,
        key: str,
    ) -> str:
        parts = [prompt]

        if style:
            parts.append(f"曲风：{style}")

        if tempo:
            parts.append(f"速度约为 {tempo} BPM")

        if key:
            parts.append(f"调性：{key}")

        return "；".join(parts)

    @staticmethod
    def _parse_key(key: str) -> tuple[str, str]:
        """
        Parse common user inputs:
            "C major"
            "C Major"
            "A# minor"
            "A# Minor"

        Returns:
            (key_name, "Major"/"Minor")
        """
        normalized = " ".join(key.strip().split())

        if not normalized:
            return "", ""

        parts = normalized.split(" ", 1)
        key_name = parts[0]
        mode = ""

        if len(parts) == 2:
            raw_mode = parts[1].strip().lower()
            if raw_mode.startswith("minor"):
                mode = "Minor"
            elif raw_mode.startswith("major"):
                mode = "Major"

        return key_name, mode

    def _wait_for_song(
        self,
        task_id: str,
    ) -> dict[str, Any]:
        """Poll QuerySong until success or failure."""
        started = time.monotonic()

        while True:
            elapsed = time.monotonic() - started

            if elapsed >= self.task_timeout:
                raise CompositionError(
                    f"Song generation timed out after "
                    f"{self.task_timeout:.0f} seconds."
                )

            response = self._request(
                action="QuerySong",
                body={
                    "TaskID": task_id,
                },
            )

            if response.get("Code") != 0:
                raise CompositionError(
                    f"QuerySong failed: "
                    f"{response.get('Message') or response}"
                )

            result = response.get("Result") or {}
            status = result.get("Status")
            progress = result.get("Progress")

            logger.debug(
                "QuerySong task=%s status=%s progress=%s",
                task_id,
                status,
                progress,
            )

            # Official states:
            # 0 -> waiting
            # 1 -> processing
            # 2 -> success
            # 3 -> failure
            if status == 2:
                return result.get("SongDetail") or {}

            if status == 3:
                failure = result.get("FailureReason") or {}
                code = failure.get("Code")
                message = failure.get("Msg") or "unknown error"

                if code:
                    message = f"{message} (code={code})"

                raise CompositionError(
                    f"Song generation failed: {message}"
                )

            time.sleep(self.poll_interval)

    def _request(
        self,
        action: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Signed POST request to the Volcengine OpenAPI endpoint."""
        query = {
            "Action": action,
            "Version": self.api_version,
        }

        body_bytes = json.dumps(
            body,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        headers = self.signer.sign(
            method="POST",
            uri="/",
            query=query,
            body=body_bytes,
            host=self.host,
        )

        url = f"https://{self.host}/"

        try:
            response = self.session.post(
                url,
                params=query,
                data=body_bytes,
                headers=headers,
                timeout=(15, 45),
            )
        except requests.RequestException as exc:
            raise CompositionError(
                f"Could not reach Volcengine: {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise CompositionError(
                "Volcengine returned non-JSON response."
            ) from exc

        if not response.ok:
            raise CompositionError(
                f"Volcengine HTTP {response.status_code}: {data}"
            )

        return data

    def _download_audio(
        self,
        remote_audio_url: str,
    ) -> str:
        """
        Download the temporary/platform audio URL into our own
        static/generated directory, as required by the platform docs.
        """
        self.generated_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        filename = f"{uuid.uuid4().hex}.mp3"
        output_path = self.generated_dir / filename

        try:
            with self.session.get(
                remote_audio_url,
                stream=True,
                timeout=(15, 120),
            ) as response:
                response.raise_for_status()

                with output_path.open("wb") as output:
                    for chunk in response.iter_content(
                        chunk_size=1024 * 1024,
                    ):
                        if chunk:
                            output.write(chunk)

        except requests.RequestException as exc:
            output_path.unlink(missing_ok=True)

            raise CompositionError(
                f"Failed to download generated audio: {exc}"
            ) from exc

        except OSError as exc:
            output_path.unlink(missing_ok=True)

            raise CompositionError(
                f"Failed to save generated audio: {exc}"
            ) from exc

        logger.info(
            "Generated audio saved to %s",
            output_path,
        )

        return f"/static/generated/{filename}"
