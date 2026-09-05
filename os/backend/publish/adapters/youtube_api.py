from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class YouTubeAPIClient:
    def __init__(self):
        self.status = "initialized"
        self.credentials = None
        self.service = None

    def initialize(self, credentials=None):
        self.credentials = credentials or {}

        access_token = self.credentials.get("access_token")
        refresh_token = self.credentials.get("refresh_token")

        if access_token:
            try:
                self.credentials = Credentials(
                    token=access_token,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                )
                self.service = build(
                    "youtube",
                    "v3",
                    credentials=self.credentials,
                )
            except Exception:
                self.service = None

        self.status = "ready"
        return {
            "platform": "youtube",
            "status": "ready"
        }

    def upload_video(self, video_path, title, description, privacy_status="public"):
        if not self.service:
            return {
                "platform": "youtube",
                "status": "not_configured"
            }

        try:
            media = MediaFileUpload(video_path, resumable=True)
            request = self.service.videos().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": title,
                        "description": description,
                    },
                    "status": {
                        "privacyStatus": privacy_status,
                    },
                },
                media_body=media,
            )

            response = request.execute()
            video_id = response.get("id")

            return {
                "platform": "youtube",
                "status": "published",
                "video_id": video_id,
                "url": f"https://youtube.com/watch?v={video_id}" if video_id else None,
            }
        except Exception as error:
            return {
                "platform": "youtube",
                "status": "failed",
                "error": str(error),
            }

    def get_video_status(self, video_id):
        if not self.service:
            return {
                "video_id": video_id,
                "status": "not_configured"
            }

        return {
            "video_id": video_id,
            "status": "processing"
        }

    def delete_video(self, video_id):
        if not self.service:
            return {
                "status": "not_configured"
            }

        return {
            "status": "ready_for_delete"
        }
