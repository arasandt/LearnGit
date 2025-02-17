# import requests
# import multiprocessing
# import time
# from datetime import datetime

# base_url = "http://10.104.146.218/"
# # base_url = "http://10.104.146.219/"


# def invoke(urls):
#     url, loop, wait = urls
#     for i in range(loop):
#         response = requests.get(url)
#         print(f"{datetime.now()}: {response.status_code} ==> {url} ")
#         time.sleep(wait)
#         # print(f"{datetime.now()} : {loop} ==> {url} ")


# def common_invocations(app):
#     # Define URLs to invoke in parallel
#     urls = [
#         (f"{base_url}{app}/", 1, 0),
#         (f"{base_url}{app}/health", 1, 0),
#         (f"{base_url}{app}/login?username=subscriber&password=subscriber", 9, 5),
#         (f"{base_url}{app}/login?username=admin&password=admin", 2, 5),
#     ]

#     # Execute all requests in parallel using process pool
#     pool = multiprocessing.Pool(processes=10)
#     pool.map(invoke, urls)
#     pool.close()
#     pool.join()


# app = "nexusapp"
# common_invocations(app)

# app = "nobleapp"
# common_invocations(app)


import requests
import multiprocessing
import time
from typing import List, Tuple
from dataclasses import dataclass
from urllib.parse import urljoin
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    # base_url: str = "http://10.104.146.218/"
    base_url: str = "http://10.104.146.219/"
    max_processes: int = 10


class URLInvoker:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def invoke(self, url_config: Tuple[str, int, int]) -> None:
        """Execute HTTP GET requests based on configuration.

        Args:
            url_config: Tuple containing (url, number_of_loops, wait_time in seconds)
        """
        url, loops, wait_time = url_config
        for count in range(loops):
            try:
                response = requests.get(url)
                logger.info(
                    f"Loop {count + 1} : Status {response.status_code} => {url}"
                )
                # logger.info(f"Loop {count + 1} => {url}")
                time.sleep(wait_time)
            except requests.RequestException as e:
                logger.error(f"Error accessing {url}: {str(e)}")

    def get_url_configurations(self, app_name: str) -> List[Tuple[str, int, int]]:
        """Generate URL configurations for the given app.

        Args:
            app_name: Name of the application

        Returns:
            List of tuples containing (url, loops, wait_time)
        """
        return [
            (urljoin(self.base_url, f"{app_name}/"), 1, 0),
            (urljoin(self.base_url, f"{app_name}/health"), 1, 0),
            (
                urljoin(
                    self.base_url,
                    f"{app_name}/login?username=subscriber&password=subscriber",
                ),
                5,
                30,
            ),
            (
                urljoin(
                    self.base_url, f"{app_name}/login?username=admin&password=admin"
                ),
                2,
                30,
            ),
            (
                urljoin(
                    self.base_url, f"{app_name}/login?username=trial&password=trial"
                ),
                15,
                30,
            ),
        ]

    def execute_invocations(self, app_name: str) -> None:
        """Execute all invocations for an app in parallel.

        Args:
            app_name: Name of the application
        """
        urls = self.get_url_configurations(app_name)

        with multiprocessing.Pool(processes=Config.max_processes) as pool:
            pool.map(self.invoke, urls)


def main():
    invoker = URLInvoker(Config.base_url)

    apps = ["nexusapp", "nobleapp"]
    processes = []
    logger.info(f"Starting invocations for {apps}")

    for app in apps:
        p = multiprocessing.Process(target=invoker.execute_invocations, args=(app,))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    logger.info(f"Completed invocations for {apps}")


if __name__ == "__main__":
    main()
    # add a big fiel to trigger disk alert alarm
    # stop nginx to trigger slo breach alarm
