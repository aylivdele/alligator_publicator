import os


class Settings:
    INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    INSTAGRAM_IG_USER_ID = os.getenv("INSTAGRAM_IG_USER_ID")


settings = Settings()