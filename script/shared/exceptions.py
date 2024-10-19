class VoteMarketProofsException(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class VoteMarketDataException(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message
