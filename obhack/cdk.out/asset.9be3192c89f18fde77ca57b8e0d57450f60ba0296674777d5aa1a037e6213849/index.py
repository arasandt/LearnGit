import boto3
import os
from boto3.dynamodb.conditions import Attr
from datetime import datetime, UTC, timedelta

apps = os.getenv("APPS")

cloudwatch = boto3.client("cloudwatch")


def lambda_handler(event, context):
    print("Received event: ", event)

    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(minutes=5)
    for app in apps.split(","):
        if app == "nobleapp":
            response = cloudwatch.get_metric_data(
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
            response = cloudwatch.get_metric_data(
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
        timestamps = response["MetricDataResults"][0]["Timestamps"]

        # Count requests with latency < 300ms (0.3 seconds)
        count_below_300ms = sum(1 for v in latency_values if v < 0.3)

        cloudwatch.put_metric_data(
            Namespace=f"{app}_CustomMetrics",
            MetricData=[
                {
                    "MetricName": "PercentageRequestsBelow300ms",
                    "Value": count_below_300ms / sum(latency_values),
                    "Unit": "Count",
                    "Timestamp": end_time,
                }
            ],
        )

    print("Processing Complete")
