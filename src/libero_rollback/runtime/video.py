"""Annotated MP4 recorder for rollback episodes (B / D suites).

Every control step gets one video frame (agentview + wrist camera) with a
readable status panel.  An injection or trigger decision is rendered as a
one-second highlighted card at the exact step where it happened, so the video
shows *when* the rollback was injected and *what* the state delta was.  This is
the video evidence required by ``docs/SPEC.md`` §5 / README §6.3 (20 fps,
H.264 / yuv420p / faststart, 1 s injection card).

The recorder is optional (``--video``) and needs the ``runtime`` extra
(numpy + Pillow) plus either PyAV or imageio-ffmpeg for encoding.  PyAV is
preferred because it encodes in-process: forking an ffmpeg subprocess after JAX
has been initialised can deadlock the model process.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
except ImportError as error:  # pragma: no cover - exercised only on the CPU-only env
    raise ImportError(
        "libero_rollback.runtime.video requires the 'runtime' extra "
        "(numpy + Pillow); install the simulation/extras environment first"
    ) from error

from collections.abc import Mapping
from typing import Any


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


class _PyAvWriter:
    """In-process H.264 writer (PyAV), avoiding the ffmpeg subprocess fork."""

    def __init__(self, path: str | Path, fps: int, width: int, height: int) -> None:
        import av

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.container = av.open(str(self.path), "w")
        self.stream = self.container.add_stream("libx264", rate=int(fps))
        self.stream.width = int(width)
        self.stream.height = int(height)
        self.stream.pix_fmt = "yuv420p"

    def append_data(self, frame) -> None:
        import av
        import numpy as np

        array = np.ascontiguousarray(np.asarray(frame, dtype=np.uint8))
        video_frame = av.VideoFrame.from_ndarray(array, format="rgb24")
        for packet in self.stream.encode(video_frame):
            self.container.mux(packet)

    def close(self) -> None:
        try:
            for packet in self.stream.encode():
                self.container.mux(packet)
        finally:
            self.container.close()


class AnnotatedVideoRecorder:
    """Streaming MP4 writer with a status panel and injection decision cards."""

    WIDTH = 720
    HEIGHT = 900
    IMAGE = 512
    WRIST = 192

    def __init__(self, path: str | Path, fps: int = 20, card_seconds: float = 1.0) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fps = max(1, int(fps))
        self.card_frames = max(1, int(round(self.fps * card_seconds)))
        try:
            self.writer = _PyAvWriter(self.path, self.fps, self.WIDTH, self.HEIGHT)
        except Exception:
            # Fallback for environments without PyAV.  This starts an ffmpeg
            # subprocess; callers that run after JAX initialisation should
            # prefer PyAV (installed in the openpi environment).
            import imageio.v2 as imageio

            self.writer = imageio.get_writer(
                str(self.path),
                fps=self.fps,
                codec="libx264",
                quality=8,
                pixelformat="yuv420p",
                macro_block_size=None,
            )
        self.frames = 0
        self.font_small = _font(16)
        self.font = _font(20)
        self.font_bold = _font(24)
        self.font_title = _font(24)
        self.log_lines: deque[tuple[str, tuple[int, int, int]]] = deque(maxlen=9)

    def _base(self, agentview: np.ndarray, wrist: np.ndarray | None) -> Image.Image:
        canvas = Image.new("RGB", (self.WIDTH, self.HEIGHT), (12, 12, 14))
        agent = Image.fromarray(
            np.ascontiguousarray(np.asarray(agentview, dtype=np.uint8)[::-1])
        )
        agent = agent.resize((self.IMAGE, self.IMAGE), Image.BILINEAR)
        canvas.paste(agent, (0, 0))
        if wrist is not None:
            hand = Image.fromarray(
                np.ascontiguousarray(np.asarray(wrist, dtype=np.uint8)[::-1])
            )
            hand = hand.resize((self.WRIST, self.WRIST), Image.BILINEAR)
            canvas.paste(hand, (self.IMAGE, 0))
        draw = ImageDraw.Draw(canvas)
        draw.text(
            (self.IMAGE + 8, self.WRIST + 10),
            "wrist camera",
            font=self.font_small,
            fill=(170, 170, 180),
        )
        draw.text(
            (8, self.IMAGE - 24), "agentview", font=self.font_small, fill=(230, 230, 230)
        )
        return canvas

    def _panel(
        self,
        canvas: Image.Image,
        *,
        title: str,
        lines: list[tuple[str, tuple[int, int, int], Any]],
        highlight: tuple[int, int, int] | None = None,
    ) -> Image.Image:
        draw = ImageDraw.Draw(canvas)
        panel_top = self.IMAGE
        draw.rectangle([0, panel_top, self.WIDTH, self.HEIGHT], fill=(14, 14, 18))
        draw.line([0, panel_top, self.WIDTH, panel_top], fill=(60, 60, 70), width=2)
        if highlight:
            draw.rectangle(
                [4, panel_top + 4, self.WIDTH - 4, self.HEIGHT - 4],
                outline=highlight,
                width=4,
            )
        draw.text((18, panel_top + 12), title, font=self.font_title, fill=(245, 245, 250))
        y = panel_top + 56
        for text, color, font in lines:
            draw.text((18, y), text, font=font, fill=color)
            y += 30 if font is self.font_small else 36
        return canvas

    def _fit_text(self, text: Any, font: Any, max_width: int) -> str:
        text = str(text)
        measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        if measure.textlength(text, font=font) <= max_width:
            return text
        ell = "..."
        while text and measure.textlength(text + ell, font=font) > max_width:
            text = text[:-1]
        return text + ell

    def add_log(self, text: str, color: tuple[int, int, int] = (190, 200, 215)) -> None:
        """Append one persistent line to the video event log."""

        self.log_lines.append((str(text), color))

    def clear_log(self) -> None:
        self.log_lines.clear()

    def _write_image(self, image: Image.Image) -> None:
        self.writer.append_data(np.asarray(image, dtype=np.uint8))
        self.frames += 1

    def step(
        self,
        agentview: np.ndarray,
        wrist: np.ndarray | None,
        *,
        step: int,
        stage: str,
        horizon_index: int,
        last_decision: Mapping[str, Any] | None = None,
        success: bool = False,
        title: str | None = None,
        policy_label: str | None = None,
        controller_label: str | None = None,
    ) -> None:
        """Draw one frame with a non-overlapping rolling event log."""

        title = title or "LIBERO-Rollback"
        canvas = self._base(agentview, wrist)
        draw = ImageDraw.Draw(canvas)
        panel_top = self.IMAGE
        draw.rectangle([0, panel_top, self.WIDTH, self.HEIGHT], fill=(14, 14, 18))
        draw.line([0, panel_top, self.WIDTH, panel_top], fill=(60, 60, 70), width=2)
        draw.text(
            (18, panel_top + 10),
            self._fit_text(title, self.font_title, self.WIDTH - 36),
            font=self.font_title,
            fill=(245, 245, 250),
        )

        y = panel_top + 48
        header = f"step {step:4d}   horizon {horizon_index}   " + (
            "SUCCESS" if success else "running"
        )
        draw.text((18, y), header, font=self.font, fill=(235, 235, 240))
        y += 28
        draw.text(
            (18, y),
            self._fit_text(f"stage: {stage}", self.font, self.WIDTH - 36),
            font=self.font,
            fill=(210, 220, 235),
        )
        y += 28
        controller = controller_label or policy_label or "unknown"
        draw.text(
            (18, y),
            self._fit_text(f"controller: {controller}", self.font, self.WIDTH - 36),
            font=self.font,
            fill=(120, 220, 170),
        )
        y += 26
        draw.text(
            (18, y),
            f"frames={self.frames}  fps={self.fps}",
            font=self.font_small,
            fill=(130, 130, 140),
        )
        y += 24
        if last_decision and last_decision.get("line"):
            draw.text(
                (18, y),
                self._fit_text(
                    f"last decision: {last_decision['line']}",
                    self.font_small,
                    self.WIDTH - 36,
                ),
                font=self.font_small,
                fill=(255, 220, 130),
            )
            y += 22
        draw.text((18, y), "event log (latest):", font=self.font_small, fill=(150, 160, 175))
        y += 22
        entries = list(self.log_lines)
        if not entries:
            entries = [("waiting for trigger / injection events", (120, 125, 135))]
        for text, color in entries:
            draw.text(
                (18, y),
                self._fit_text(text, self.font_small, self.WIDTH - 36),
                font=self.font_small,
                fill=color,
            )
            y += 21
        self._write_image(canvas)

    def render_event_card(
        self,
        agentview: np.ndarray,
        wrist: np.ndarray | None,
        *,
        title: str,
        lines: list[tuple[str, tuple[int, int, int], Any]],
        highlight: tuple[int, int, int] = (120, 200, 255),
    ) -> list[np.ndarray]:
        image = self._panel(
            self._base(agentview, wrist), title=title, lines=lines, highlight=highlight
        )
        return [np.asarray(image, dtype=np.uint8) for _ in range(self.card_frames)]

    def event_card(
        self,
        agentview: np.ndarray,
        wrist: np.ndarray | None,
        *,
        title: str,
        lines: list[tuple[str, tuple[int, int, int], Any]],
        highlight: tuple[int, int, int] = (120, 200, 255),
    ) -> None:
        for frame in self.render_event_card(
            agentview, wrist, title=title, lines=lines, highlight=highlight
        ):
            self.writer.append_data(frame)
            self.frames += 1

    def close(self) -> None:
        if self.writer is not None:
            self.writer.close()
            self.writer = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
