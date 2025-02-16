import boto3
import os
from boto3.dynamodb.conditions import Attr
from datetime import datetime, UTC, timedelta

# dynamodb_client = boto3.client("dynamodb")
# dynamodb_resource = boto3.resource("dynamodb")


def lambda_handler(event, context):
    print("Received event: ", event)

    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(minutes=5)

    print("Processing Complete")
