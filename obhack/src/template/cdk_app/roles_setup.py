from aws_cdk import (
    aws_iam as iam,
    aws_ssm as ssm,
)
from constructs import Construct
from .base import BaseStack


class RolesStack(BaseStack):

    def create_lambda_role_and_send_to_ssm(self, role_name=None):
        """
        Create Lambda Roles and send it to SSM
        """

        if role_name is None:
            return

        role = iam.Role(
            self,
            f"{self.config.namespace}{role_name}",
            role_name=f"{self.config.namespace}{role_name}",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description=f"Role for {role_name}",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchFullAccess"),
            ],
        )

        self.output_role_to_ssm(role=role, role_name=role_name)

    def create_ec2_role_and_send_to_ssm(self, role_name=None):
        """
        Create EC2 Roles and send it to SSM
        """

        if role_name is None:
            return

        role = iam.Role(
            self,
            f"{self.config.namespace}{role_name}",
            role_name=f"{self.config.namespace}{role_name}",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description=f"Role for {role_name}",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSXRayDaemonWriteAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "CloudWatchAgentServerPolicy"
                ),
            ],
        )

        # Add CloudWatch PutMetricData policy to the role
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
            )
        )

        self.output_role_to_ssm(role=role, role_name=role_name)

    def output_role_to_ssm(self, role=None, role_name=None):
        ssm.StringParameter(
            self,
            f"{self.config.namespace}{role_name}ssm",
            parameter_name=f"{self.ssm_prefix}/{role_name}",
            string_value=role.role_arn,
        )

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """
        Initialization for CDK
        """

        super().__init__(scope, construct_id, **kwargs)

        for role in [
            "instance",
            #     "process_events_lambda",
            #     "knowledgebase_sync_lambda",
            #     "opensearch_index_lambda",
            #     "streamlit_invoke_lambda",
            #     "event_explainer_lambda",
        ]:
            self.create_ec2_role_and_send_to_ssm(role_name=role)

        for role in ["bucket_deployment", "custommetrics"]:
            self.create_lambda_role_and_send_to_ssm(role_name=role)
