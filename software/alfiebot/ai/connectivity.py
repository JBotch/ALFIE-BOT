"""Is the internet there? For now this only knows about the simulator's
"simulate internet failure" switch; a real check arrives with the cloud
provider (Phase 4). Local features never depend on it."""


class Connectivity:
    def __init__(self):
        self.simulate_offline = False

    @property
    def online(self) -> bool:
        return not self.simulate_offline

    @property
    def status(self) -> str:
        return "offline (simulated)" if self.simulate_offline else "online"
