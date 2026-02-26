import boto3
from botocore.exceptions import ClientError
from datetime import timedelta


class S3Storage:
    def __init__(self, endpoint_url: str, access_key_id: str, access_key: str, bucket_name: str, region: str):
        self.bucket_name = bucket_name
        self.client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=access_key,
        region_name=region,
    )

    def upload_file(self, local_path: str, key: str) -> str:
        self.client.upload_file(local_path, self.bucket_name, key)
        return key

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": key
                },
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            raise RuntimeError(f"Failed to generate URL: {e}")