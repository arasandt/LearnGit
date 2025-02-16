import boto3
import os
from boto3.dynamodb.conditions import Attr

# dynamodb_client = boto3.client("dynamodb")
# dynamodb_resource = boto3.resource("dynamodb")


def lambda_handler(event, context):
    print("Received event: ", event)

    # application_table = os.getenv("APPLICATION_TABLE")

    # app_table = dynamodb_resource.Table(application_table)

    # print("Testing : put_item")
    # response = app_table.put_item(
    #     Item={
    #         "applicationid": "APP1",
    #         "applicationname": "EDCS",
    #         "applicationstatus": "active",
    #     }
    # )
    # print(response)
    # response = app_table.put_item(
    #     Item={
    #         "applicationid": "APP2",
    #         "applicationname": "AMTS",
    #         "applicationstatus": "inactive",
    #     }
    # )
    # print(response)
    # response = app_table.put_item(
    #     Item={
    #         "applicationid": "APP3",
    #         "applicationname": "KAPS",
    #         "applicationstatus": "inactive",
    #     }
    # )
    # print(response)
    # response = app_table.put_item(
    #     Item={
    #         "applicationid": "APP4",
    #         "applicationname": "UCRS",
    #         "applicationstatus": "active",
    #     }
    # )
    # print(response)

    # print("Testing : get_item")
    # response = app_table.get_item(Key={"applicationid": "APP4"})
    # print(response)
    # response = dynamodb_client.get_item(
    #     TableName=application_table, Key={"applicationid": {"S": "APP4"}}
    # )
    # print(response)

    # print("Testing : delete_item")
    # response = app_table.delete_item(Key={"applicationid": "APP4"})
    # print(response)

    # print("Testing : scan")
    # response = dynamodb_client.scan(
    #     TableName=application_table,
    #     ExpressionAttributeNames={"#APP": "applicationid"},
    #     ExpressionAttributeValues={":v": {"S": "active"}},
    #     FilterExpression="applicationstatus = :v",
    #     ProjectionExpression="#APP",
    # )
    # print(response)
    # response = app_table.scan(FilterExpression=Attr("applicationstatus").eq("inactive"))
    # print(response)

    print("Processing Complete")
