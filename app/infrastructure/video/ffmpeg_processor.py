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

            
# ─── Безопасные, почти незаметные диапазоны ───
            brightness    = round(random.uniform(-0.006, 0.006), 4)   # ±0.6%
            contrast      = round(random.uniform(0.992, 1.008), 4)    # ±0.8%
            saturation    = round(random.uniform(0.992, 1.008), 4)
            hue_shift     = round(random.uniform(-0.8, 0.8), 3)       # градусы, очень мало
            noise_level   = random.randint(1, 4)                      # 1–4 — ниже порога глаза

            # Масштаб — сильно уменьшаем или убираем совсем (лучше без него)
            scale_var     = random.uniform(1.00, 1.015)               # max 1.5% — почти незаметно
            # Или вообще убрать scale, если видео не требует

            # Скорость — если оставляешь, то ±3–4% максимум, иначе заметно
            speed_var     = random.uniform(0.96, 1.04)                # сузили диапазон

            vf_parts = []

            # Цвет + шум — обязательно
            vf_parts.append(
                f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation},"
                f"hue=h={hue_shift},noise=alls={noise_level}:allf=t+p"
            )

            # Scale — только если очень хочешь (лучше убрать или 1–1.5%)
            if scale_var > 1.005:
                vf_parts.append(
                    f"scale=trunc(iw*{scale_var}/2)*2:trunc(ih*{scale_var}/2)*2:flags=lanczos"
                )  # lanczos лучше качества, чем fast_bilinear

            # setpts
            vf_parts.append(f"setpts={1/speed_var}*PTS")

            vf = ",".join(vf_parts)

            # Аудио: atempo + лёгкий шум/громкость
            af = f"atempo={speed_var},volume={random.uniform(-0.4,0.4)}dB,afftdn"  # afftdn = noise reduction

            # Перекодирование — ключевой фактор уникальности
            crf         = random.randint(17, 23)          # разные артефакты сжатия
            preset      = random.choice(["medium", "slow", "veryslow"])  # разные motion estimation
            bitrate_var = random.choice([None, f"-b:v {random.randint(2800,4500)}k"])

            cmd = [
                "ffmpeg", "-i", input_path,
                "-vf", vf,
                "-af", af,
                "-c:v", "libx264",
                "-preset", preset,
                "-crf", str(crf),
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-y"
            ]

            if bitrate_var:
                cmd.extend(bitrate_var.split())

            cmd.append(output_path)

            subprocess.run(cmd, check=True)
            output_files.append(on_generate(output_path))

        return output_files