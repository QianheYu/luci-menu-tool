class Registry:
    def __init__(self):
        self._parsers = {}
        self._appliers = {}

    def register(self, mode: str, parser_cls: type, applier_cls: type):
        self._parsers[mode] = parser_cls
        self._appliers[mode] = applier_cls

    def get_parser(self, mode: str):
        if mode not in self._parsers:
            raise ValueError(f"Unknown mode: {mode}")
        return self._parsers[mode]()

    def get_applier(self, mode: str):
        if mode not in self._appliers:
            raise ValueError(f"Unknown mode: {mode}")
        return self._appliers[mode]()


registry = Registry()
