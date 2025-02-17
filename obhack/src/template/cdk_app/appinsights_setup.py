from aws_cdk import (
    aws_applicationinsights as applicationinsights,
    aws_resourcegroups as resourcegroups,
)
from constructs import Construct
from .base import BaseStack


class AppInsightsStack(BaseStack):

    def create_application_insights(self):
        cfn_group = resourcegroups.CfnGroup(
            self,
            f"{self.config.namespace}resources",
            name=f"{self.config.namespace}resources",
            description=f"Resource group for {self.app_stack_name} stack",
            resource_query=resourcegroups.CfnGroup.ResourceQueryProperty(
                query=resourcegroups.CfnGroup.QueryProperty(
                    resource_type_filters=["AWS::AllSupported"],
                    stack_identifier=self.app_stack_id,
                ),
                type="CLOUDFORMATION_STACK_1_0",
            ),
        )

        application = applicationinsights.CfnApplication(
            self,
            f"{self.config.namespace}application",
            resource_group_name=f"{self.config.namespace}resources",
            auto_configuration_enabled=False,
            attach_missing_permission=False,
            cwe_monitor_enabled=True,
            ops_center_enabled=True,
            component_monitoring_settings=[
                applicationinsights.CfnApplication.ComponentMonitoringSettingProperty(
                    component_arn=f"arn:aws:ec2:{self.config.region}:{self.config.account}:instance/{self.app_component_name}",
                    component_configuration_mode="DEFAULT",
                    tier="DEFAULT",
                )
            ],
        )

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """
        Initialization for CDK
        """

        super().__init__(scope, construct_id, **kwargs)

        observability_stack = "observabilitystack"

        self.app_stack_id = self.from_ssm(
            f"/{self.config.namespace}/{observability_stack}/appinsightsstackid"
        )
        self.app_stack_name = self.from_ssm(
            f"/{self.config.namespace}/{observability_stack}/appinsightsstackname"
        )
        self.app_component_name = self.from_ssm(
            f"/{self.config.namespace}/{observability_stack}/appinsightscomponentname"
        )

        self.create_application_insights()
