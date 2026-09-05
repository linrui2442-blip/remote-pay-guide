class TextProvider:
    def initialize(self):
        return {"provider":"text","status":"ready"}

    def request(self, request):
        return {"status":"completed","provider":"text","output":{"echo":request.prompt}}
