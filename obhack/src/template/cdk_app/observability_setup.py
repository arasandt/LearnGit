# import shutil
# import os

from aws_cdk import (
    RemovalPolicy,
    Duration,
    Size,
    Fn,
    CfnTag,
    aws_rum as rum,
    aws_cloudtrail as cloudtrail,
    aws_kms as kms,
    aws_sns as sns,
    aws_s3 as s3,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_ec2 as ec2,
    aws_logs as logs,
    aws_cognito as cognito,
    aws_events_targets as events_targets,
    aws_sns_subscriptions as subs,
    aws_s3_deployment as s3deploy,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions,
    aws_synthetics as synthetics,
    aws_applicationsignals as applicationsignals,
    aws_lambda as lambda_,
    aws_events as events,
    aws_events_targets as targets,
)
from constructs import Construct
from .base import BaseStack
import json
import sys
import os
from pathlib import Path


class ObservabilityStack(BaseStack):
    def assign_permissions(self):
        """
        Add permissions to the resources
        """
        pass

        self.activity_topic = sns.Topic(
            self,
            f"{self.config.namespace}topic",
            topic_name=self.config.namespace,
            master_key=self.activity_key,
        )

    def create_keys(self, roles=[]):
        self.generic_key = kms.Key(
            self,
            f"{self.config.namespace}key",
            alias=self.config.namespace,
            enable_key_rotation=False,
            removal_policy=RemovalPolicy.DESTROY,
            pending_window=Duration.days(7),
            admins=[
                iam.AccountPrincipal(account_id=self.account),
            ],
            policy=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        principals=[
                            iam.ServicePrincipal("cloudtrail.amazonaws.com"),
                            iam.ServicePrincipal("s3.amazonaws.com"),
                            iam.ServicePrincipal("ec2.amazonaws.com"),
                            iam.ServicePrincipal("sns.amazonaws.com"),
                            iam.ServicePrincipal("events.amazonaws.com"),
                            iam.ServicePrincipal("cloudwatch.amazonaws.com"),
                            iam.ServicePrincipal("sqs.amazonaws.com"),
                            # Provide access to Superadmin role too
                            iam.Role.from_role_arn(
                                self,
                                "superadminrole",
                                f"arn:aws:iam::{self.config.account}:role/Superadmin",
                            ),
                            *roles,
                        ],
                        actions=["kms:*"],
                        resources=["*"],
                    )
                ]
            ),
        )

    def output_to_ssm(self):
        ssm.StringParameter(
            self,
            f"{self.config.namespace}keyssm",
            parameter_name=f"{self.ssm_prefix}/key",
            string_value=self.activity_key.key_arn,
        )

        ssm.StringParameter(
            self,
            f"{self.config.namespace}topicssm",
            parameter_name=f"{self.ssm_prefix}/topic",
            string_value=self.activity_topic.topic_arn,
        )

        ssm.StringParameter(
            self,
            f"{self.config.namespace}bucketssm",
            parameter_name=f"{self.ssm_prefix}/bucket",
            string_value=self.activity_bucket.bucket_name,
        )

    def create_ec2(self):
        user_data = self.template_rendering(
            script=self.config.init_script,
            vars={
                "namespace": self.config.namespace,
                "region": self.config.region,
                "build_bucket": self.build_bucket.bucket_name,
                "nginx_apps": "("
                + " ".join([f'"{i}"' for i in self.config.nginx_apps.keys()])
                + ")",
            },
            files={"cloudwatch_agent_config": self.config.cloudwatch_agent_config},
        )
        # print(user_data)

        # self.alpha_instance = ec2.Instance(
        #     self,
        #     f"{self.config.namespace}alpha",
        #     instance_name=f"{self.config.namespace}alpha",
        #     vpc=self.vpc,
        #     detailed_monitoring=True,
        #     instance_type=ec2.InstanceType.of(
        #         ec2.InstanceClass.M5, ec2.InstanceSize.LARGE
        #     ),
        #     machine_image=ec2.AmazonLinuxImage(
        #         generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
        #     ),
        #     associate_public_ip_address=False,
        #     role=self.instance_role,
        #     vpc_subnets=ec2.SubnetSelection(
        #         subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
        #     ),
        #     propagate_tags_to_volume_on_creation=True,
        #     block_devices=[
        #         ec2.BlockDevice(
        #             device_name="/dev/xvda",
        #             volume=ec2.BlockDeviceVolume.ebs(
        #                 30,
        #                 volume_type=ec2.EbsDeviceVolumeType.GP3,
        #                 encrypted=False,
        #                 # kms_key=self.generic_key,
        #                 delete_on_termination=True,
        #             ),
        #         )
        #     ],
        #     user_data=ec2.UserData.custom(user_data),
        #     security_group=self.alpha_instance_sg,
        #     ssm_session_permissions=True,
        #     user_data_causes_replacement=True,
        #     # private_ip_address=self.config.instance_static_ip,
        #     # network_interfaces=[
        #     #     {
        #     #         "deviceIndex": "0",
        #     #         "networkInterfaceId": network_interface.ref,
        #     #         "deleteOnTermination": True,
        #     #     }
        #     # ],
        # )

        self.alpha_instance = ec2.CfnInstance(
            self,
            f"{self.config.namespace}alpha",
            instance_type="m5.large",
            image_id=ec2.AmazonLinuxImage(
                generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
            )
            .get_image(self)
            .image_id,
            # subnet_id=self.vpc.private_subnets[0].subnet_id,
            iam_instance_profile=iam.CfnInstanceProfile(
                self,
                f"{self.config.namespace}alphainstanceprofile",
                roles=[self.instance_role.role_name],
            ).ref,
            monitoring=True,
            block_device_mappings=[
                ec2.CfnInstance.BlockDeviceMappingProperty(
                    device_name="/dev/xvda",
                    ebs=ec2.CfnInstance.EbsProperty(
                        volume_size=30,
                        volume_type="gp3",
                        delete_on_termination=True,
                        encrypted=False,
                    ),
                )
            ],
            # security_group_ids=[self.alpha_instance_sg.security_group_id],
            user_data=Fn.base64(user_data),
            propagate_tags_to_volume_on_creation=True,
            tags=[
                CfnTag(
                    key="Name",
                    value=f"{self.config.namespace}alpha",
                )
            ],
            network_interfaces=[
                ec2.CfnInstance.NetworkInterfaceProperty(
                    device_index="0",
                    group_set=[self.alpha_instance_sg.security_group_id],
                    subnet_id=self.vpc.private_subnets[0].subnet_id,
                    private_ip_addresses=[
                        ec2.CfnInstance.PrivateIpAddressSpecificationProperty(
                            primary=False,
                            private_ip_address=self.config.instance_static_ip,
                        )
                    ],
                )
            ],
        )

    def create_notification_topic(self):
        """
        This function will create SNS topic
        """
        self.notification_topic = sns.Topic(
            self,
            f"{self.config.namespace}notificationtopic",
            topic_name=f"{self.config.namespace}notificationtopic",
            master_key=self.generic_key,
        )

        self.notification_topic.add_subscription(
            subs.EmailSubscription("arasandt@virtusa.com")
        )

    def create_security_groups(self):
        """
        This function will create security groups
        """

        self.alpha_instance_sg = ec2.SecurityGroup(
            self,
            f"{self.config.namespace}alphasg",
            security_group_name=f"{self.config.namespace}alphasg",
            allow_all_outbound=True,
            vpc=self.vpc,
        )
        self.alpha_instance_sg.connections.allow_from(
            ec2.Peer.ipv4("10.0.0.0/8"),
            ec2.Port.tcp(80),
            "Allow HTTP for Nginx",
        )
        self.alpha_instance_sg.connections.allow_from(
            ec2.Peer.ipv4("10.0.0.0/8"),
            ec2.Port.tcp(8080),
            "Allow HTTP for Tomcat",
        )

    def create_cloudwatch_metrics_and_alarms(
        self,
    ):
        """
        This function will create cloudwatch metric and alarm
        """
        instance_networkin_metric = cloudwatch.Metric(
            metric_name="NetworkIn",
            statistic="avg",
            label="Network In",
            namespace=f"AWS/EC2",
            dimensions_map={"InstanceId": self.alpha_instance.attr_instance_id},
        )

        instance_networkout_metric = cloudwatch.Metric(
            metric_name="NetworkOut",
            statistic="avg",
            label="Network Out",
            namespace=f"AWS/EC2",
            dimensions_map={"InstanceId": self.alpha_instance.attr_instance_id},
        )

        instance_ebs_read_metric = cloudwatch.Metric(
            metric_name="EBSReadBytes",
            statistic="Sum",
            label="EBSRead",
            namespace="AWS/EC2",
            dimensions_map={"InstanceId": self.alpha_instance.attr_instance_id},
        )

        instance_ebs_write_metric = cloudwatch.Metric(
            metric_name="EBSWriteBytes",
            statistic="Sum",
            label="EBSWrite",
            namespace="AWS/EC2",
            dimensions_map={"InstanceId": self.alpha_instance.attr_instance_id},
        )

        instance_ebs_throughput_metric = cloudwatch.MathExpression(
            expression="((m1 + m2) / PERIOD(m1)) / 1024",
            using_metrics={
                "m1": instance_ebs_read_metric,
                "m2": instance_ebs_write_metric,
            },
            label="kb/sec",
            period=Duration.minutes(5),
        )

        instance_disk_used_metric = cloudwatch.Metric(
            metric_name="disk_used_percent",
            statistic="avg",
            label="Disk Used (%)",
            namespace=f"{self.config.namespace}",
            dimensions_map={"InstanceId": self.alpha_instance.attr_instance_id},
        )

        instance_disk_used_errors = cloudwatch.Alarm(
            self,
            metric=instance_disk_used_metric,
            id=f"{self.config.namespace}alphadiskusederrors",
            alarm_name=f"{self.config.namespace}alphadiskusederrors",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            evaluation_periods=3,
            threshold=50,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            datapoints_to_alarm=3,
        )

        instance_disk_used_errors.add_alarm_action(
            aws_cloudwatch_actions.SnsAction(self.notification_topic)
        )

        instance_mem_used_metric = cloudwatch.Metric(
            metric_name="mem_used_percent",
            statistic="avg",
            label="Memory Used (%)",
            namespace=f"{self.config.namespace}",
            dimensions_map={"InstanceId": self.alpha_instance.attr_instance_id},
        )

        instance_mem_used_errors = cloudwatch.Alarm(
            self,
            metric=instance_mem_used_metric,
            id=f"{self.config.namespace}alphamemusederrors",
            alarm_name=f"{self.config.namespace}alphamemusederrors",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            evaluation_periods=3,
            threshold=50,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            datapoints_to_alarm=3,
        )

        instance_mem_used_errors.add_alarm_action(
            aws_cloudwatch_actions.SnsAction(self.notification_topic)
        )

        instance_cpu_usage_active_metric = cloudwatch.Metric(
            metric_name="cpu_usage_active",
            statistic="avg",
            label="CPU Used (%)",
            namespace=f"{self.config.namespace}",
            dimensions_map={"InstanceId": self.alpha_instance.attr_instance_id},
        )

        instance_cpu_usage_active_errors = cloudwatch.Alarm(
            self,
            metric=instance_cpu_usage_active_metric,
            id=f"{self.config.namespace}alphacpuusageactiveerrors",
            alarm_name=f"{self.config.namespace}alphacpuusageactiveerrors",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            evaluation_periods=3,
            threshold=50,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            datapoints_to_alarm=3,
        )

        instance_cpu_usage_active_errors.add_alarm_action(
            aws_cloudwatch_actions.SnsAction(self.notification_topic)
        )

        cpu_utilization_metric = cloudwatch.Metric(
            namespace="AWS/EC2",
            metric_name="CPUUtilization",
            dimensions_map={"InstanceId": self.alpha_instance.attr_instance_id},
            statistic="Maximum",
            period=Duration.minutes(2),
        )

        # Running Status (1 = Running, Green)
        instance_running_metric = cloudwatch.MathExpression(
            expression="IF(FILL(m1,0) > 0, 1, 0)",
            using_metrics={"m1": cpu_utilization_metric},
            label="RUNNING",
            period=Duration.minutes(2),
            color=cloudwatch.Color.GREEN,
        )

        # Down Status (0 = Down, Red)
        instance_down_metric = cloudwatch.MathExpression(
            expression="IF(FILL(m1,0) == 0, 1, 0)",
            using_metrics={"m1": cpu_utilization_metric},
            label="STOPPED",
            period=Duration.minutes(2),
            color=cloudwatch.Color.RED,
        )

        instance_down_metric_errors = cloudwatch.Alarm(
            self,
            metric=instance_down_metric,
            id=f"{self.config.namespace}alphadownerrors",
            alarm_name=f"{self.config.namespace}alphadownerrors",
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
            evaluation_periods=1,
            threshold=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            datapoints_to_alarm=1,
        )

        instance_down_metric_errors.add_alarm_action(
            aws_cloudwatch_actions.SnsAction(self.notification_topic)
        )

        app_widgets = []

        alive_expressions = []
        alive_metrics = {}

        for count, app in enumerate(self.config.nginx_apps.keys()):
            if app == "nobleapp":  # Instrumented through Application Signals
                dimensions_map = {"Environment": "ec2:default", "Service": app}
                namespace = "ApplicationSignals"
                latency_metric_key = "Latency"
                fault_metric_key = "Fault"
                dimensions_map_requests = dimensions_map | {
                    "GroupName": "Default",
                    "ServiceType": "AWS::EC2::Instance",
                    "ServiceName": app,
                }
                del dimensions_map_requests["Service"]
            else:
                dimensions_map = {
                    "ServiceName": app,
                    "GroupName": "Default",
                    "ServiceType": "NONE",
                }
                namespace = "AWS/X-Ray"
                latency_metric_key = "ResponseTime"
                fault_metric_key = "FaultRate"
                dimensions_map_requests = dimensions_map

            xray_faults_metric = cloudwatch.Metric(
                namespace=namespace,
                metric_name=fault_metric_key,
                dimensions_map=dimensions_map,
                statistic="Sum",
                period=Duration.minutes(5),
            )

            xray_fault_rate_expression_metric = cloudwatch.MathExpression(
                expression="FILL(m1, 0)",  # Compute % fault rate, filling missing values with 0
                using_metrics={"m1": xray_faults_metric},
                label="Faults",
                color="#d62728",
            )

            xray_latency_metric = cloudwatch.Metric(
                namespace=namespace,
                metric_name=latency_metric_key,
                dimensions_map=dimensions_map,
                statistic="Average",
                period=Duration.minutes(5),
            )

            if app == "nobleapp":
                xray_latency_metric_new = cloudwatch.MathExpression(
                    expression="m1 / 1000",
                    using_metrics={"m1": xray_latency_metric},
                    label="Latency",
                )
            else:
                xray_latency_metric_new = xray_latency_metric

            xray_requests_metric = cloudwatch.Metric(
                namespace="AWS/X-Ray",
                metric_name="TracedRequestCount",
                dimensions_map=dimensions_map_requests,
                statistic="Sum",
                period=Duration.minutes(5),
            )

            requests_below_300ms_metric = cloudwatch.Metric(
                namespace=f"{app}_CustomMetrics",
                metric_name="PercentageRequestsBelow300ms",
                dimensions_map={
                    "Derived": "PercentageRequestsBelow300ms",
                },
                statistic="Average",
                period=Duration.minutes(5),
            )
            requests_below_300ms_expression_metric = cloudwatch.MathExpression(
                expression="m1 * 100",
                using_metrics={"m1": requests_below_300ms_metric},
                label="Percentage",
            )

            username_trial_custom_metric = cloudwatch.Metric(
                namespace=f"{app}_CustomMetrics",
                metric_name="usercount",
                dimensions_map={
                    "Annotation": "trial",
                },
                statistic="Sum",
                period=Duration.minutes(5),
            )

            username_trial_custom_metric_anamoly = cloudwatch.Metric(
                namespace=f"{app}_CustomMetrics",
                metric_name="usercount",
                dimensions_map={"Annotation": "trial"},
                statistic="p90",
            )

            username_trial_custom_metric_anamoly_detection = cloudwatch.MathExpression(
                expression="ANOMALY_DETECTION_BAND(m1, 2)",
                label="Anomaly Detection Band",
                using_metrics={"m1": username_trial_custom_metric_anamoly},
            )

            # username_trial_custom_metric_anamoly_detection_alarm = cloudwatch.CfnAlarm(
            #     self,
            #     metrics=[
            #         username_trial_custom_metric_anamoly,
            #         username_trial_custom_metric_anamoly_detection,
            #     ],
            #     id=f"{self.config.namespace}{app}trialanomalydetectoralarm",
            #     alarm_name=f"{self.config.namespace}{app}trialanomalydetectoralarm",
            #     comparison_operator="GREATER_THAN_UPPER_THRESHOLD",
            #     threshold=2,
            #     evaluation_periods=3,
            #     datapoints_to_alarm=2,
            #     treat_missing_data="NOT_BREACHING",
            #     period=5,
            # )

            # cfn_alarm = (
            #     username_trial_custom_metric_anamoly_detection_alarm.node.default_child
            # )
            # cfn_alarm.add_property_deletion_override("Threshold")
            # cfn_alarm.add_property_override("ThresholdMetricId", "expr_1")

            username_trial_custom_metric_anamoly_detection_alarm = cloudwatch.CfnAlarm(
                self,
                id=f"{self.config.namespace}{app}trialanomalydetectoralarm",
                alarm_name=f"{self.config.namespace}{app}trialanomalydetectoralarm",
                comparison_operator="GreaterThanUpperThreshold",
                evaluation_periods=3,
                datapoints_to_alarm=2,
                # period=Duration.minutes(5).to_seconds(),
                treat_missing_data="notBreaching",
                metrics=[
                    {
                        "id": "m1",
                        "metricStat": {
                            "metric": {
                                "namespace": f"{app}_CustomMetrics",
                                "metricName": "usercount",
                                "dimensions": [
                                    {"name": "Annotation", "value": "trial"}
                                ],
                            },
                            "period": Duration.minutes(5).to_seconds(),
                            "stat": "p90",
                        },
                        "returnData": True,
                    },
                    {
                        "id": "expr_1",
                        "expression": "ANOMALY_DETECTION_BAND(m1, 2)",
                        "label": "Anomaly Detection Band",
                        "returnData": True,
                    },
                ],
                threshold_metric_id="expr_1",
            )

            # username_trial_custom_metric_anamoly_detection_alarm.add_alarm_action(
            #     aws_cloudwatch_actions.SnsAction(self.notification_topic)
            # )

            # username_trial_custom_metric_anamoly = cloudwatch.CfnAnomalyDetector(
            #     self,
            #     f"{self.config.namespace}{app}trialanomalydetector",
            #     # metric_name=username_trial_custom_metric.metric_name,
            #     # namespace=username_trial_custom_metric.namespace,
            #     # stat="p90",
            #     single_metric_anomaly_detector=cloudwatch.CfnAnomalyDetector.SingleMetricAnomalyDetectorProperty(
            #         dimensions=[
            #             cloudwatch.CfnAnomalyDetector.DimensionProperty(
            #                 name="Annotation", value="trial"
            #             )
            #         ],
            #         metric_name="usercount",
            #         namespace=f"{app}_CustomMetrics",
            #         stat="p90",
            #     ),
            # )

            # username_trial_custom_metric_anamoly_alarm = cloudwatch.CfnAlarm(
            #     self,
            #     f"{app}trialanomalyalarm",
            #     alarm_name=f"{app}trialanomalyalarm",
            #     evaluation_periods=1,
            #     threshold_metric_id=f"{app}MetricExpression",
            #     datapoints_to_alarm=1,
            #     comparison_operator="GreaterThanUpperThreshold",
            #     treat_missing_data="ignore",
            #     alarm_description=f"Anomaly detection alarm for {app} trial users",
            #     metrics=[
            #         {
            #             "Id": "m1",
            #             "MetricStat": {
            #                 "Metric": {
            #                     "Namespace": f"{app}_CustomMetrics",
            #                     "MetricName": "usercount",
            #                     "Dimensions": [{"Name": "Annotation", "Value": "trial"}],
            #                 },
            #                 "Period": Duration.minutes(5).to_seconds(),
            #                 "Stat": "p90",
            #             },
            #             "ReturnData": True,
            #         },
            #         {
            #             "Id": "ad1",
            #             "Expression": "ANOMALY_DETECTION_BAND(m1, 2)",
            #             "ReturnData": True,
            #         },
            #     ],
            # )

            username_subscriber_custom_metric = cloudwatch.Metric(
                namespace=f"{app}_CustomMetrics",
                metric_name="usercount",
                dimensions_map={
                    "Annotation": "subscriber",
                },
                statistic="Sum",
                period=Duration.minutes(5),
            )

            slo_attainment_metric = cloudwatch.Metric(
                namespace="AWS/ApplicationSignals",
                metric_name="AttainmentRate",
                dimensions_map={
                    "SloName": f"{self.config.namespace}{app}availabilityslo",
                },
                statistic="Average",
                period=Duration.minutes(5),
            )

            slo_attainment_metric_alarm = cloudwatch.Alarm(
                self,
                metric=slo_attainment_metric,
                id=f"{self.config.namespace}{app}availabilitysloalarm",
                alarm_name=f"{self.config.namespace}{app}availabilitysloalarm",
                treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
                evaluation_periods=3,
                threshold=99,
                comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            )

            slo_attainment_metric_alarm.add_alarm_action(
                aws_cloudwatch_actions.SnsAction(self.notification_topic)
            )

            api_success_metric = cloudwatch.Metric(
                namespace="CloudWatchSynthetics",
                metric_name="SuccessPercent",
                dimensions_map={"CanaryName": f"{self.config.namespace}{app}api"},
                statistic="Maximum",
                period=Duration.minutes(5),
            )
            api_down_expression_metric = cloudwatch.MathExpression(
                expression="IF(FILL(m1,0) == 0, 1, 0)",
                using_metrics={"m1": api_success_metric},
                label="Service Down",
                period=Duration.minutes(5),
                color=cloudwatch.Color.RED,
            )
            api_up_expression_metric = cloudwatch.MathExpression(
                expression="IF(FILL(m1,0) > 0, 1, 0)",
                using_metrics={"m1": api_success_metric},
                label="Service Up",
                period=Duration.minutes(5),
                color=cloudwatch.Color.GREEN,
            )

            if app == "nobleapp":
                volume_metric = cloudwatch.Metric(
                    namespace="AWS/X-Ray",
                    metric_name="ResponseTime",
                    dimensions_map={
                        "GroupName": "Default",
                        "ServiceName": app,
                        "Environment": "ec2:default",
                        "ServiceType": "AWS::EC2::Instance",
                    },
                    statistic="SampleCount",
                    period=Duration.minutes(5),
                )
            else:
                volume_metric = cloudwatch.Metric(
                    namespace="AWS/X-Ray",
                    metric_name="ResponseTime",
                    dimensions_map=dimensions_map,
                    statistic="SampleCount",
                    period=Duration.minutes(5),
                )

            alive_metrics.update({f"m{count+1}": volume_metric})
            alive_expressions.append(f"IF(FILL(m{count+1},0) > 0, 1, 0)")

            availability_metric = cloudwatch.MathExpression(
                expression="(volume - fault) * 100 / volume",
                using_metrics={
                    "volume": xray_requests_metric,
                    "fault": xray_faults_metric,
                },
                label="Availability",
                period=Duration.minutes(5),
            )

            app_widgets.append(
                cloudwatch.Row(
                    cloudwatch.Column(
                        cloudwatch.TextWidget(
                            background=cloudwatch.TextWidgetBackground.TRANSPARENT,
                            markdown="---",
                            height=1,
                            width=24,
                        ),
                    ),
                    cloudwatch.Column(
                        cloudwatch.TextWidget(
                            background=cloudwatch.TextWidgetBackground.TRANSPARENT,
                            markdown=f"""# **{app}**
* **InstanceId:** {self.alpha_instance.attr_instance_id}
* **AZ:** {self.alpha_instance.attr_availability_zone} 
* **IP:** {self.alpha_instance.attr_private_ip}
* **URL:** [Click here](http://{self.config.instance_static_ip}{app})
""",
                            height=4,
                            width=4,
                        ),
                        cloudwatch.GraphWidget(
                            title="Service Status",
                            left=[api_down_expression_metric, api_up_expression_metric],
                            view=cloudwatch.GraphWidgetView.PIE,
                            period=Duration.minutes(5),
                            set_period_to_time_range=False,
                            height=4,
                            width=4,
                            legend_position=cloudwatch.LegendPosition.HIDDEN,
                        ),
                    ),
                    cloudwatch.Column(
                        cloudwatch.GraphWidget(
                            title="Placeholder",
                            left=[availability_metric],
                            left_y_axis=cloudwatch.YAxisProps(min=0),
                            stacked=False,
                            live_data=False,
                            height=4,
                            width=5,
                            view=cloudwatch.GraphWidgetView.TIME_SERIES,
                        ),
                        cloudwatch.SingleValueWidget(
                            title="Requests < 300ms",
                            metrics=[requests_below_300ms_expression_metric],
                            set_period_to_time_range=True,
                            height=4,
                            width=5,
                        ),
                    ),
                    cloudwatch.Column(
                        cloudwatch.GraphWidget(
                            title="Trial vs Subscribed Users",
                            left=[
                                username_trial_custom_metric,
                                username_subscriber_custom_metric,
                            ],
                            left_y_axis=cloudwatch.YAxisProps(min=0),
                            stacked=False,
                            live_data=False,
                            height=4,
                            width=5,
                            view=cloudwatch.GraphWidgetView.TIME_SERIES,
                            legend_position=cloudwatch.LegendPosition.RIGHT,
                        ),
                        cloudwatch.GraphWidget(
                            title="Availability",
                            left=[availability_metric],
                            left_y_axis=cloudwatch.YAxisProps(min=0),
                            stacked=False,
                            live_data=False,
                            height=4,
                            width=5,
                            view=cloudwatch.GraphWidgetView.TIME_SERIES,
                        ),
                    ),
                    cloudwatch.Column(
                        cloudwatch.GraphWidget(
                            title="SLO attainment Availability",
                            left=[slo_attainment_metric],
                            left_y_axis=cloudwatch.YAxisProps(
                                max=100, show_units=False, label="%"
                            ),
                            stacked=False,
                            live_data=False,
                            height=4,
                            width=5,
                            period=Duration.minutes(60),
                            view=cloudwatch.GraphWidgetView.TIME_SERIES,
                        ),
                        cloudwatch.GraphWidget(
                            title="Requests and Faults (5xx)",
                            left=[
                                xray_requests_metric,
                                xray_fault_rate_expression_metric,
                            ],
                            left_y_axis=cloudwatch.YAxisProps(min=0),
                            stacked=False,
                            live_data=False,
                            height=4,
                            width=5,
                            view=cloudwatch.GraphWidgetView.TIME_SERIES,
                        ),
                    ),
                    cloudwatch.Column(
                        cloudwatch.GraphWidget(
                            title="Trial Users Anomaly",
                            left=[username_trial_custom_metric_anamoly],
                            # left=[username_trial_custom_metric_anamoly_detection],
                            left_y_axis=cloudwatch.YAxisProps(min=0),
                            height=4,
                            width=5,
                        ),
                        cloudwatch.GraphWidget(
                            title="Latency",
                            left=[xray_latency_metric_new],
                            left_y_axis=cloudwatch.YAxisProps(min=0, label="Seconds"),
                            stacked=False,
                            live_data=False,
                            height=4,
                            width=5,
                            view=cloudwatch.GraphWidgetView.TIME_SERIES,
                        ),
                    ),
                ),
            )

        total_alive_metric = cloudwatch.MathExpression(
            expression="+".join(alive_expressions),
            using_metrics=alive_metrics,
            label="Count",
            period=Duration.minutes(1),
        )

        self.dashboard.add_widgets(
            cloudwatch.Row(
                cloudwatch.Column(
                    cloudwatch.GraphWidget(
                        title="Instance Health",
                        left=[instance_running_metric, instance_down_metric],
                        view=cloudwatch.GraphWidgetView.PIE,
                        period=Duration.minutes(1),
                        set_period_to_time_range=False,
                        width=4,
                        height=6,
                        legend_position=cloudwatch.LegendPosition.BOTTOM,
                    )
                ),
                cloudwatch.Column(
                    cloudwatch.SingleValueWidget(
                        title="Services",
                        metrics=[total_alive_metric],
                        set_period_to_time_range=True,
                        width=3,
                        height=3,
                    ),
                    cloudwatch.SingleValueWidget(
                        title="Disk Throughput",
                        metrics=[instance_ebs_throughput_metric],
                        set_period_to_time_range=True,
                        width=3,
                        height=3,
                    ),
                ),
                cloudwatch.Column(
                    cloudwatch.SingleValueWidget(
                        title="Instance Metrics (Average)",
                        metrics=[
                            instance_disk_used_metric,
                            instance_mem_used_metric,
                            instance_cpu_usage_active_metric,
                        ],
                        set_period_to_time_range=True,
                        width=17,
                        height=3,
                    ),
                    cloudwatch.SingleValueWidget(
                        title="Instance Metrics (Average)",
                        metrics=[
                            instance_networkin_metric,
                            instance_networkout_metric,
                        ],
                        set_period_to_time_range=True,
                        width=17,
                        height=3,
                    ),
                ),
            ),
            *app_widgets,
        )

    def create_cloudwatch_dashboard(self):
        self.dashboard = cloudwatch.Dashboard(
            self,
            f"{self.config.namespace}dashboard",
            dashboard_name=f"{self.config.namespace}dashboard",
            period_override=cloudwatch.PeriodOverride.AUTO,
            start="-PT1D",
        )

    def create_buckets(self):
        self.build_bucket = s3.Bucket(
            self,
            f"{self.config.namespace}-{self.config.account}buildbucket",
            bucket_name=f"{self.config.namespace}build-{self.config.account}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.generic_key,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

    def build_apps(self, apps):
        for name in apps:
            # # Create a temporary directory for zipping
            # os.makedirs(f"{self.config.code_location}/tmp", exist_ok=True)

            # # Create zip file
            # shutil.make_archive(
            #     f"{self.config.code_location}/tmp/{name}",
            #     "zip",
            #     f"{self.config.code_location}/{name}",
            # )

            s3deploy.BucketDeployment(
                self,
                f"{self.config.namespace}{name}",
                sources=[s3deploy.Source.asset(f"{self.config.code_location}/{name}")],
                destination_bucket=self.build_bucket,
                destination_key_prefix=name,
                memory_limit=2048,
                ephemeral_storage_size=Size.mebibytes(10240),
                role=self.bucket_deployments_role,
                extract=False,
            )

    def create_cognito(self):
        self.identity_pool = cognito.CfnIdentityPool(
            self,
            f"{self.config.namespace}rumidentitypool",
            identity_pool_name=f"{self.config.namespace}rumidentitypool",
            allow_unauthenticated_identities=True,  # Required for AWS RUM
        )

        self.unauthenticated_role = iam.Role(
            self,
            f"{self.config.namespace}rumunauthenticatedrole",
            role_name=f"{self.config.namespace}rumunauthenticatedrole",
            assumed_by=iam.FederatedPrincipal(
                "cognito-identity.amazonaws.com",
                {
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": self.identity_pool.ref
                    }
                },
                "sts:AssumeRoleWithWebIdentity",
            ),
            description="IAM Role for Unauthenticated Users in Cognito Identity Pool",
        )

        # Attach AWS RUM Policy to Unauthenticated Role
        self.unauthenticated_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonCloudWatchRUMFullAccess"
            )
        )

        cognito.CfnIdentityPoolRoleAttachment(
            self,
            f"{self.config.namespace}rumidentitypoolroleattachment",
            identity_pool_id=self.identity_pool.ref,
            roles={"unauthenticated": self.unauthenticated_role.role_arn},
        )

    def upload_app_env_vars(self):
        for count, app in enumerate(self.config.nginx_apps.keys()):
            ssm.StringParameter(
                self,
                f"{self.config.namespace}{app}envvars",
                allowed_pattern=".*",
                description=f"Environment variables for {app}",
                parameter_name=f"/{self.config.namespace}/{app}",
                string_value=json.dumps(
                    {
                        "app": app,
                        "account_id": self.config.account,
                        "region": self.config.region,
                        "rum_identity_pool_id": self.identity_pool.ref,
                        "rum_role_arn": self.unauthenticated_role.role_arn,
                        "rum_app_id": self.rum_monitor.attr_id,
                    }
                ),
            )

    def create_rum_monitor(self):
        self.rum_monitor = rum.CfnAppMonitor(
            self,
            f"{self.config.namespace}monitor",
            name=f"{self.config.namespace}monitor",
            domain=self.config.instance_static_ip,
            cw_log_enabled=True,
            app_monitor_configuration=rum.CfnAppMonitor.AppMonitorConfigurationProperty(
                enable_x_ray=True,
                session_sample_rate=1,
                telemetries=["errors", "performance", "http"],
                guest_role_arn=self.unauthenticated_role.role_arn,
                identity_pool_id=self.identity_pool.ref,
            ),
        )

    def create_synthetic_monitor(self):
        self.all_synthetic_monitors = []
        for app in self.config.nginx_apps.keys():
            # Heartbeat Monitoring Canary
            heartbeat_canary = synthetics.Canary(
                self,
                f"{self.config.namespace}{app}hb",
                canary_name=f"{self.config.namespace}{app}hb",
                runtime=synthetics.Runtime.SYNTHETICS_PYTHON_SELENIUM_3_0,
                provisioned_resource_cleanup=True,
                test=synthetics.Test.custom(
                    code=synthetics.Code.from_asset(
                        os.path.join(self.config.code_location, "canary")
                    ),
                    handler="index.handler",
                ),
                # active_tracing=True, # RuntimeError: You can only enable active tracing for canaries that use canary runtime version `syn-nodejs-2.0` or later.
                memory=Size.mebibytes(1024),
                schedule=synthetics.Schedule.rate(Duration.minutes(5)),
                environment_variables={
                    "URL": f"http://{self.config.instance_static_ip}/{app}",
                    "CANARY_TYPE": "HEARTBEAT",
                },
                vpc=self.vpc,
                vpc_subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                ),
            )

            api_canary = synthetics.Canary(
                self,
                f"{self.config.namespace}{app}api",
                canary_name=f"{self.config.namespace}{app}api",
                runtime=synthetics.Runtime.SYNTHETICS_PYTHON_SELENIUM_3_0,
                test=synthetics.Test.custom(
                    code=synthetics.Code.from_asset(
                        os.path.join(self.config.code_location, "canary")
                    ),
                    handler="index.handler",
                ),
                memory=Size.mebibytes(1024),
                schedule=synthetics.Schedule.rate(Duration.minutes(5)),
                environment_variables={
                    "URL": f"http://{self.config.instance_static_ip}/{app}/health",
                    "CANARY_TYPE": "API",
                },
                vpc=self.vpc,
                vpc_subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                ),
            )

            # self.all_synthetic_monitors.append(synthetic_monitor)

        workflow_canary = synthetics.Canary(
            self,
            f"{self.config.namespace}workflow",
            canary_name=f"{self.config.namespace}workflow",
            runtime=synthetics.Runtime.SYNTHETICS_NODEJS_PUPPETEER_8_0,
            test=synthetics.Test.custom(
                code=synthetics.Code.from_asset(
                    os.path.join(self.config.code_location, "canary")
                ),
                handler="index.handler",
            ),
            memory=Size.mebibytes(1024),
            schedule=synthetics.Schedule.rate(Duration.minutes(5)),
            environment_variables={
                "URL": f"http://{self.config.instance_static_ip}/",
                "CANARY_TYPE": "WORKFLOW",
                "NAVIGATION_APP": "nobleapp",
            },
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
        )

    def create_signal_slos(self):
        for app in self.config.nginx_apps.keys():
            if (
                app == "nexusapp"
            ):  # open telemetry not running for this app so cannot do SLOs
                continue

            #  LATENCY SLO - Ensure 95% of requests complete within 1s
            latency_slo = applicationsignals.CfnServiceLevelObjective(
                self,
                f"{self.config.namespace}{app}latencyslo",
                name=f"{self.config.namespace}{app}latencyslo",
                burn_rate_configurations=[
                    applicationsignals.CfnServiceLevelObjective.BurnRateConfigurationProperty(
                        look_back_window_minutes=60
                    )
                ],
                goal=applicationsignals.CfnServiceLevelObjective.GoalProperty(
                    attainment_goal=95,  # 95% of requests should meet latency target
                    interval=applicationsignals.CfnServiceLevelObjective.IntervalProperty(
                        rolling_interval=applicationsignals.CfnServiceLevelObjective.RollingIntervalProperty(
                            duration=1, duration_unit="DAY"
                        )
                    ),
                    warning_threshold=90,  # Warning if < 90% meet latency goal
                ),
                sli=applicationsignals.CfnServiceLevelObjective.SliProperty(
                    comparison_operator="LessThan",
                    metric_threshold=1,  # 1s latency threshold
                    sli_metric=applicationsignals.CfnServiceLevelObjective.SliMetricProperty(
                        key_attributes={
                            "Environment": "ec2:default",
                            "Name": app,
                            "Type": "Service",
                        },
                        metric_type="LATENCY",
                        operation_name="GET /",
                        period_seconds=60,
                        statistic="p95",  # 95th percentile latency
                    ),
                ),
            )

            # AVAILABILITY SLO - Ensure 99.9% uptime for /health endpoint
            availability_slo = applicationsignals.CfnServiceLevelObjective(
                self,
                f"{self.config.namespace}{app}availabilityslo",
                name=f"{self.config.namespace}{app}availabilityslo",
                goal=applicationsignals.CfnServiceLevelObjective.GoalProperty(
                    attainment_goal=99.9,  # 99.9% uptime goal
                    interval=applicationsignals.CfnServiceLevelObjective.IntervalProperty(
                        rolling_interval=applicationsignals.CfnServiceLevelObjective.RollingIntervalProperty(
                            duration=7, duration_unit="DAY"
                        )
                    ),
                    warning_threshold=99,  # Warning if uptime drops below 99%
                ),
                sli=applicationsignals.CfnServiceLevelObjective.SliProperty(
                    comparison_operator="GreaterThanOrEqualTo",
                    metric_threshold=99.9,  # Expected uptime percentage
                    sli_metric=applicationsignals.CfnServiceLevelObjective.SliMetricProperty(
                        key_attributes={
                            "Environment": "ec2:default",
                            "Name": app,
                            "Type": "Service",
                        },
                        metric_type="AVAILABILITY",
                        operation_name="GET /health",
                        period_seconds=60,
                    ),
                ),
            )

    def create_log_anomaly_detector(self):
        log_anamoly_detector = logs.CfnLogAnomalyDetector(
            self,
            f"{self.config.namespace}gunicornanamoly",
            anomaly_visibility_time=7,
            detector_name=f"{self.config.namespace}gunicornanamoly",
            evaluation_frequency="FIFTEEN_MIN",
            filter_pattern="Admin login not allowed",
            log_group_arn_list=[
                f"arn:aws:logs:{self.config.region}:{self.config.account}:log-group:{self.config.namespace}-gunicorn-error-logs:*"
            ],
        )

        log_anamoly_detector_metric = cloudwatch.Metric(
            metric_name="AnomalyCount",
            statistic="Average",
            label="Log Anomaly",
            namespace="AWS/Logs",
            dimensions_map={
                "LogAnomalyDetector": log_anamoly_detector.detector_name,
                "LogAnomalyPriority": "HIGH",
            },
        )

        log_anamoly_detector_metric_alarm = cloudwatch.Alarm(
            self,
            metric=log_anamoly_detector_metric,
            id=f"{self.config.namespace}gunicornanamolyalarm",
            alarm_name=f"{self.config.namespace}gunicornanamolyalarm",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            evaluation_periods=1,
            threshold=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            datapoints_to_alarm=1,
        )

        log_anamoly_detector_metric_alarm.add_alarm_action(
            aws_cloudwatch_actions.SnsAction(self.notification_topic)
        )

    def create_custommetrics_lambda(self):
        """
        This function will pull metric to create another metric
        """
        lambda_attribute_name = "_".join(
            sys._getframe().f_code.co_name.split("_")[1:]
        ).lower()
        lambda_original_name = "_".join(lambda_attribute_name.split("_")[:-1])
        lambda_name = f"{self.config.namespace}{lambda_original_name}"

        asset_location = str(
            Path(self.config.code_location).joinpath(lambda_original_name)
        )
        self.logger.info(f"Code Location for lambda {lambda_name}: {asset_location}")

        lambda_function = lambda_.Function(
            self,
            lambda_name,
            function_name=lambda_name,
            code=lambda_.Code.from_asset(asset_location),
            handler="index.lambda_handler",
            timeout=Duration.seconds(30),
            memory_size=128,
            tracing=lambda_.Tracing.ACTIVE,
            runtime=self.python_runtime,
            role=self.custommetrics_role,
        )

        lambda_function.add_environment("APPS", ",".join(self.config.nginx_apps))

        setattr(
            self,
            lambda_attribute_name,
            self.common_setup_for_lambda(lambda_function, lambda_name, asset_location),
        )

        # Create an EventBridge rule to schedule the Lambda function
        rule = events.Rule(
            self,
            f"{lambda_name}rule",
            rule_name=f"{lambda_name}",
            schedule=events.Schedule.cron(minute="*/5", hour="*"),
        )

        rule.add_target(
            targets.LambdaFunction(
                lambda_function,
                event=events.RuleTargetInput.from_object({"Message": "Start"}),
            )
        )

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """
        Initialization for CDK
        """

        super().__init__(scope, construct_id, **kwargs)

        roles_stack = "rolesstack"

        self.instance_role = iam.Role.from_role_arn(
            self,
            id=f"{self.config.namespace}{roles_stack}instancesssm",
            role_arn=self.from_ssm(f"/{self.config.namespace}/{roles_stack}/instance"),
        )

        self.bucket_deployments_role = iam.Role.from_role_arn(
            self,
            id=f"{self.config.namespace}{roles_stack}bucket_deploymentssm",
            role_arn=self.from_ssm(
                f"/{self.config.namespace}/{roles_stack}/bucket_deployment"
            ),
        )

        self.custommetrics_role = iam.Role.from_role_arn(
            self,
            id=f"{self.config.namespace}{roles_stack}custommetricsssm",
            role_arn=self.from_ssm(
                f"/{self.config.namespace}/{roles_stack}/custommetrics"
            ),
        )

        self.create_keys([self.instance_role, self.bucket_deployments_role])

        self.create_notification_topic()

        self.create_cognito()

        self.create_buckets()

        self.build_apps(self.config.nginx_apps.keys())

        self.create_rum_monitor()

        self.upload_app_env_vars()

        self.create_security_groups()

        self.create_ec2()

        self.create_synthetic_monitor()

        self.create_signal_slos()

        self.create_cloudwatch_dashboard()

        self.create_log_anomaly_detector()

        self.create_cloudwatch_metrics_and_alarms()

        self.create_custommetrics_lambda()

        # self.assign_permissions()

        # self.output_to_ssm()
