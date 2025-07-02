import json


class GameResponse:
    def __init__(self, message):
        self.message = message

    def toJSON(self):
        return json.dumps(
            self,
            default=lambda o: o.__dict__,
            sort_keys=True,
            indent=4)


class UserError(GameResponse):
    def __init__(self, message):
        super().__init__(message)

class NotFoundError(GameResponse):
    def __init__(self, message):
        super().__init__(message)

class SuccessResponse(GameResponse):
    def __init__(self, message, notice = ""):
        self.__notice = notice
        super().__init__(message)

    def toJSON(self):
        data = {
            "payload": self.message,
            "notice": self.__notice,
        }
        return json.dumps(data, sort_keys=True, indent=4)
