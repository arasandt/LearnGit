import boto3

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
