import boto3
import time, requests
from werkzeug.wrappers import Request

cw_client = boto3.client("cloudwatch", region_name="us-east-1")


def send_annotation_metric(app_name, annotation_value, count):
    response = cw_client.put_metric_data(
        Namespace=f"{app_name}_CustomMetrics",
        MetricData=[
            {
                "MetricName": "usercount",
                "Dimensions": [{"Name": "Annotation", "Value": annotation_value}],
                "Value": count,
                "Unit": "Count",
            }
        ],
    )


# Create a middleware class
class CommonMiddleware:
    def __init__(self, app):
        self.app = app
        self.latency = 0

    def __call__(self, environ, start_response):
        # Add your common middleware logic here
        request = Request(environ)
        username = request.args.get("username", "None")

        if username == "latency":
            self.latency = 0 if self.latency == 1 else 1

        # time.sleep(self.latency * 5)
        if self.latency:
            requests.get("https://10.104.146.219/nexusapp/slow")

        # Continue with the request
        return self.app(environ, start_response)
