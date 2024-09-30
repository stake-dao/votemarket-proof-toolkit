class VoteMarketProofsException(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class VoteMarketVotesException(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message
