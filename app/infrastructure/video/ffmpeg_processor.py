import subprocess
import uuid
import random
from typing import Callable
from app.domain.services import UniqueReelGenerator


class FFmpegUniqueReelGenerator(UniqueReelGenerator):

    def generate(self, input_path: str, copies: int, on_generate: Callable[[str], str]):
        output_files = []

        for _ in range(copies):
            output_path = f"/tmp/{uuid.uuid4()}.mp4"

            scale_variation = random.uniform(1.01, 1.05)
            speed_variation = random.uniform(0.99, 1.01)

            vf = (
                f"scale=trunc(iw*{scale_variation}/2)*2:trunc(ih*{scale_variation}/2)*2:flags=fast_bilinear,"
                f"setpts={1/speed_variation}*PTS"
            )

            cmd = [
                "ffmpeg",
                "-i", input_path,
                "-vf", vf,
                "-af", f"atempo={speed_variation}",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-y",
                output_path
            ]

            subprocess.run(cmd, check=True)
            output_files.append(on_generate(output_path))

        return output_files