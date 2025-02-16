import boto3
import os
from boto3.dynamodb.conditions import Attr
from datetime import datetime, UTC, timedelta

apps = os.getenv("APPS")

cw_client = boto3.client("cloudwatch")


def lambda_handler(event, context):
    print("Received event: ", event)

    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(minutes=5)
    for app in apps.split(","):
        print(f"Working on {app}")
        if app == "nobleapp":
            response = cw_client.get_metric_data(
                MetricDataQueries=[
                    {
                        "Id": "m1_latency",
                        "MetricStat": {
                            "Metric": {
                                "Namespace": "ApplicationSignals",
                                "MetricName": "Latency",
                                "Dimensions": [
                                    {"Name": "Environment", "Value": "ec2:default"},
                                    {"Name": "Service", "Value": app},
                                ],
                            },
                            "Period": 1,  # 1-second granularity
                            "Stat": "Average",
                        },
                        "ReturnData": True,
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
            )
        else:
            response = cw_client.get_metric_data(
                MetricDataQueries=[
                    {
                        "Id": "m1_latency",
                        "MetricStat": {
                            "Metric": {
                                "Namespace": "AWS/X-Ray",
                                "MetricName": "ResponseTime",
                                "Dimensions": [
                                    {"Name": "GroupName", "Value": "Default"},
                                    {"Name": "ServiceName", "Value": app},
                                    {"Name": "ServiceType", "Value": "NONE"},
                                ],
                            },
                            "Period": 1,  # 1-second granularity
                            "Stat": "Average",
                        },
                        "ReturnData": True,
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
            )

        latency_values = response["MetricDataResults"][0]["Values"]
        # timestamps = response["MetricDataResults"][0]["Timestamps"]
        print(f"Latency Values: {latency_values}")
        # Count requests with latency < 300ms (0.3 seconds)
        latency_values_below_300ms = [v for v in latency_values if v < 0.3]
        print(f"Latency Values below 300ms: {latency_values_below_300ms}")

        value = 0
        if latency_values:
            value = len(latency_values_below_300ms) / len(latency_values)

        cw_client.put_metric_data(
            Namespace=f"{app}_CustomMetrics",
            MetricData=[
                {
                    "MetricName": "PercentageRequestsBelow300ms",
                    "Value": value,
                    "Unit": "Count",
                    "Timestamp": end_time,
                }
            ],
        )

    print("Processing Complete")
