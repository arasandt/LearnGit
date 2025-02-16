from selenium.webdriver.common.by import By
from aws_synthetics.selenium import synthetics_webdriver as syn_webdriver
from aws_synthetics.common import synthetics_logger as logger
import json
import http.client
import urllib.parse

import os

URL = os.getenv("URL")
CANARY_TYPE = os.getenv("CANARY_TYPE")


def heartbeat():

    # Set screenshot option
    takeScreenshot = True

    browser = syn_webdriver.Chrome()
    browser.get(URL)

    if takeScreenshot:
        browser.save_screenshot("loaded.png")

    response_code = syn_webdriver.get_http_response(URL)
    if not response_code or response_code < 200 or response_code > 299:
        raise Exception("Failed to load page!")
    logger.info("Canary successfully executed.")


def api(method, post_data=None, headers={}):
    parsed_url = urllib.parse.urlparse(URL)
    user_agent = str(syn_webdriver.get_canary_user_agent_string())
    if "User-Agent" in headers:
        headers["User-Agent"] = f"{user_agent} {headers['User-Agent']}"
    else:
        headers["User-Agent"] = user_agent

    logger.info(
        f"Making request with Method: '{method}' URL: {URL}: Data: {json.dumps(post_data)} Headers: {json.dumps(headers)}"
    )

    if parsed_url.scheme == "https":
        conn = http.client.HTTPSConnection(parsed_url.hostname, parsed_url.port)
    else:
        conn = http.client.HTTPConnection(parsed_url.hostname, parsed_url.port)

    conn.request(method, URL, post_data, headers)
    response = conn.getresponse()
    logger.info(f"Status Code: {response.status}")
    logger.info(f"Response Headers: {json.dumps(response.headers.as_string())}")

    if not response.status or response.status < 200 or response.status > 299:
        try:
            logger.error(f"Response: {response.read().decode()}")
        finally:
            if response.reason:
                conn.close()
                raise Exception(f"Failed: {response.reason}")
            else:
                conn.close()
                raise Exception(f"Failed with status code: {response.status}")

    logger.info(f"Response: {response.read().decode()}")
    logger.info("HTTP request successfully executed.")
    conn.close()
    logger.info("Canary successfully executed.")


def handler(event, context):
    if CANARY_TYPE == "HEARTBEAT":
        logger.info("Selenium Python Heartbeat canary.")
        return heartbeat()
    elif CANARY_TYPE == "API":
        logger.info("Selenium Python API canary.")
        headers = {"Content-type": "application/json"}
        return api("GET", None, headers)
    else:
        pass

    return None
