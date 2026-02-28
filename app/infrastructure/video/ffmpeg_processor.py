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

            cmd = [
                "ffmpeg",
                "-i", input_path,
                "-vf", f"scale=iw*{scale_variation}:ih*{scale_variation}",
                "-filter:v", f"setpts={1/speed_variation}*PTS",
                "-c:a", "copy",
                "-y",
                output_path
            ]

            subprocess.run(cmd, check=True)
            output_files.append(on_generate(output_path))

        return output_files