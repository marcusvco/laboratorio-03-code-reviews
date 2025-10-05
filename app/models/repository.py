class Repository:
    def __init__(self, name, url, stars, pull_requests):
        self.name = name
        self.url = url
        self.stars = stars
        self.pull_requests = pull_requests

    def __str__(self):
        return f"Repository(name={self.name}, url={self.url}, stars={self.stars}, pull_requests={self.pull_requests[0]})"
