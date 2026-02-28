# application/use_cases/generate_unique_reels.py

import uuid
import os
from typing import List

from app.domain.services import UniqueReelGenerator
from app.infrastructure.storage.s3 import S3Storage


class ReelsUniqalizerService:

    def __init__(self, generator: UniqueReelGenerator, storage: S3Storage):
        self.generator = generator
        self.storage = storage    
        
    def on_generate(self, file_path: str) -> str:
        key = f"reels/{uuid.uuid4()}.mp4"

        self.storage.upload_file(file_path, key)
        url = self.storage.generate_presigned_url(key)

        os.remove(file_path)
        return url

    def execute(self, input_path: str, copies: int) -> List[str]:        
        return self.generator.generate(input_path, copies, self.on_generate)