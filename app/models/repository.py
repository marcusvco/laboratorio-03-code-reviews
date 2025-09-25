class Repository:
    def __init__(self, name, url, stars):
        self.name = name
        self.url = url
        self.stars = stars

    def __str__(self):
        return f"Repository(name={self.name}, url={self.url}, stars={self.stars})"
