class VideoProvider:
    def initialize(self):
        return {"provider":"video","status":"ready"}

    def request(self, request):
        return {"status":"completed","provider":"video","output":{"task":"video_generation"}}
