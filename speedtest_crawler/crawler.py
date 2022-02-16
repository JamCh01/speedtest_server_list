import asyncio
import json
from typing import Iterable

import aiohttp
import pandas
import os
import datetime

THIS_PATH = os.path.dirname(os.path.abspath(__file__))
SAVE_PATH = os.path.join(THIS_PATH, "../output")
TODAY = str(datetime.date.today())


class ServerCrawler:
    def __init__(self, t=None, r=None):
        self.t = t or 5
        self.r = r or 5
        self.task_queue = asyncio.Queue()
        self.servers = []
        self.passed = set()
        self.URL = "https://www.speedtest.net/api/js/servers"
        self.HEADERS = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.80 Safari/537.36"
        }

    async def _init_task(self):
        with open(os.path.join(THIS_PATH, "country.json"), "r", encoding="utf8") as f:
            countries = json.load(f)
        for country in countries:
            self.task_queue.put_nowait((country.get("e_name"), 0))
            self.task_queue.put_nowait((country.get("iso_3166_1_alpha_2"), 0))
            self.task_queue.put_nowait((country.get("iso_3166_1_alpha_3"), 0))

    async def fetch(self, client: aiohttp.ClientSession, search: str) -> Iterable:
        async with client.get(
            url=self.URL,
            params={
                "engine": "js",
                "search": search,
                "limit": 1000,
            },
            headers=self.HEADERS,
        ) as resp:
            assert resp.status == 200
            return iter(await resp.json())

    def __filter(self, server):
        server_id = server.get("id")
        if server_id not in self.passed:
            self.passed.add(server_id)
            return True
        else:
            return False

    async def do_request(self):
        async with aiohttp.ClientSession() as client:
            while not self.task_queue.empty():
                search, retries = await self.task_queue.get()
                if retries >= self.r:
                    continue
                try:
                    servers = await self.fetch(client=client, search=search)
                    filtered_servers = filter(self.__filter, servers)
                    for filtered_server in filtered_servers:
                        filtered_server["server_id"] = filtered_server.pop("id")
                        self.servers.append(filtered_server)

                except Exception:
                    await self.task_queue.put((search, retries + 1))

    def start(self) -> Iterable:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._init_task())
        tasks = [self.do_request() for _ in range(self.t)]
        loop.run_until_complete(asyncio.gather(*tasks))
        return iter(self.servers)


class Export:
    def __init__(self, servers: Iterable, save_path: str = None):
        self.data_frame = pandas.DataFrame(data=servers)
        self.save_path = save_path or SAVE_PATH
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)

    def to_csv(self):
        self.data_frame.to_csv(os.path.join(self.save_path, f"{TODAY}.csv"))

    def to_json(self):
        self.data_frame.to_json(
            os.path.join(self.save_path, f"{TODAY}.json"), orient="records"
        )


def main():
    sc = ServerCrawler(t=100)
    servers = sc.start()
    export = Export(servers=servers)
    export.to_json()
    export.to_csv()


if __name__ == "__main__":
    main()
