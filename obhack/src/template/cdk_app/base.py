import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_ssm as ssm,
    aws_ec2 as ec2,
    aws_lambda as lambda_,
)
from constructs import Construct
from pathlib import Path
from dotenv import dotenv_values
import subprocess
import jinja2


class BaseStack(Stack):
    def from_ssm(self, path):
        """
        This function will return ssm value for parameter
        """
        # function to get parameters stored in ssm
        return ssm.StringParameter.from_string_parameter_attributes(
            self, path, parameter_name=path
        ).string_value

    def common_setup_for_lambda(self, lambda_function, lambda_name, asset_location):
        """
        This function is for apply common properties to Lambda
        """

        # Add environment vairables
        lambda_function.add_environment("ENV", self.config.environment)
        lambda_function.add_environment("REGION", self.config.region)
        lambda_function.add_environment("NAMESPACE", self.config.namespace)
        lambda_function.add_environment("APP_NAME_TAG", self.config.app_name_tag)
        lambda_function.add_environment("MODULE_NAME_TAG", self.config.module_name_tag)
        lambda_function.add_environment("LOG_LEVEL", self.config.log_level)
        for envs in dotenv_values(Path(asset_location).joinpath(".env")).items():
            key, value = envs
            lambda_function.add_environment(key, value)

        # Set Lambda Retries
        lambda_function.configure_async_invoke(retry_attempts=0)

        # Create an CloudWatch Alarm for Lambda Failures
        # self.create_lambda_failure_cloudwatch_alarm(lambda_function, lambda_name)

        return lambda_function

    def assign_lambda_layers(self, layers=["All"]):
        if layers[0] == "All":
            lambda_layers = [layer_info[1] for layer_info in self.lambda_layers]
            return lambda_layers

        lambda_layers = []
        for layer_name in layers:
            for layer_info in self.lambda_layers:
                if layer_name in layer_info[0]:
                    lambda_layers.append(layer_info[1])
        return lambda_layers

    def create_lambda_layers(self):
        """
        This function will create lambda layers
        """
        self.lambda_layers = []

        for layer in list(filter(None, self.config.lambda_layers_build)):
            asset_location = str(Path(self.config.code_location).joinpath(layer))
            self.logger.info(f"Code Location for {layer}: {asset_location}")
            cmds = f"python3 -m pip install --platform manylinux2014_x86_64 --implementation cp  --only-binary=:all: -r {asset_location}/python/requirements.txt -t {asset_location}/python"
            # cmds = f"python3 -m pip --python {PYTHON_VERSION} install --platform manylinux2014_x86_64 --implementation cp  --only-binary=:all: -r {asset_location}/python/requirements.txt -t {asset_location}/python"
            subprocess.check_call([cmds], shell=True)
            lambda_layers_build = lambda_.LayerVersion(
                self,
                f"{self.config.namespace}{layer}layer",
                layer_version_name=f"{self.config.namespace}{layer}",
                code=lambda_.Code.from_asset(asset_location),
                compatible_runtimes=[self.python_runtime],
                compatible_architectures=[lambda_.Architecture.X86_64],
            )
            self.lambda_layers.append((layer, lambda_layers_build))

    def initialize_constants(self):
        #     """
        #     This function will initialize constants
        #     """
        #     # constants

        self.python_runtime = lambda_.Runtime.PYTHON_3_12
        self.python_version = "3.12"

        self.vpc = ec2.Vpc.from_lookup(
            self, f"{self.config.namespace}vpc", vpc_id="vpc-02509352c2f3db630"
        )

        self.certificate_arn = f"arn:aws:acm:{self.config.region}:{self.config.account}:certificate/d5d7b41d-7e70-4efa-a1a7-f67b175c77e1"

    def template_rendering(self, script, vars, files):
        """
        This function will render template
        """
        template = jinja2.Template(open(script).read())

        # First render any file content placeholders
        file_vars = {}
        for name, filepath in files.items():
            with open(filepath, "r") as f:
                file_vars[name] = f.read()
                template = jinja2.Template(template.render({**file_vars, **vars}))

        return template.render(**vars)

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """
        Initialization for CDK
        """
        self.logger = kwargs.pop("logger")
        self.config = kwargs.pop("config")

        self.ssm_prefix = "/" + construct_id.replace("-", "/").lower()

        kwargs["env"] = cdk.Environment(
            account=self.config.account, region=self.config.region
        )

        super().__init__(scope, construct_id, **kwargs)

        self.initialize_constants()
