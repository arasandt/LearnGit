"""
This is CDK Main File
"""

import sys
import os
import logging
import yaml
from pathlib import Path
import aws_cdk as cdk
from aws_cdk import Tags
from types import SimpleNamespace

from cdk_app.observability_setup import ObservabilityStack
from cdk_app.roles_setup import RolesStack
from cdk_app.appinsights_setup import AppInsightsStack

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def load_yaml_config(app_name):
    yaml_file = f"{app_name}_config.yaml"

    logger.info(f"Loading configuration from {yaml_file}")
    if os.path.exists(yaml_file):
        with open(yaml_file, "r") as config_file:
            logger.info(f"Loading configuration from {yaml_file}. Successful.")
            return yaml.safe_load(config_file)
    else:
        logger.warning(f"Loading configuration from {yaml_file}. Not found.")
        return {}


def get_environment(app):
    """Get the environment from CDK context."""
    environment = app.node.try_get_context(key="env")
    if not environment:
        raise ValueError("No context parameter passed. Expected: -c env=<environment>")
    return environment


def create_config(app, environment):
    """Create and return the configuration object."""
    env_config = app.node.try_get_context(key=environment)
    if not env_config:
        raise ValueError(f"Environment '{environment}' not found")
    namespace = env_config.get("namespace", "default")
    namespace_config = load_yaml_config(namespace)

    config = {
        "environment": environment,
        "log_level": str(logging.INFO),
        **env_config,
        **namespace_config,
    }
    return SimpleNamespace(**{k.lower(): v for k, v in config.items()})


def main():
    app = cdk.App()

    environment = get_environment(app)
    config = create_config(app, environment)
    invocation_dir = os.path.dirname(os.path.abspath(__file__))
    code_location = Path(config.code_location).resolve()

    logger.info(f"Stack Configuration         : {vars(config)}")
    logger.info(f"Environment region          : {config.region}")
    logger.info(f"Current Working Directory   : {os.getcwd()}")
    logger.info(f"Script Invocation Directory : {invocation_dir}")
    logger.info(f"Code Directory              : {code_location}")

    roles_stack = RolesStack(
        app,
        f"{config.namespace}-RolesStack",
        stack_name=f"{config.namespace}-RolesStack",
        logger=logger,
        config=config,
    )
    Tags.of(roles_stack).add("App", config.app_name_tag)
    Tags.of(roles_stack).add("Module", config.module_name_tag)
    Tags.of(roles_stack).add("Namespace", config.namespace)

    observability_stack = ObservabilityStack(
        app,
        f"{config.namespace}-ObservabilityStack",
        stack_name=f"{config.namespace}-ObservabilityStack",
        logger=logger,
        config=config,
    )
    observability_stack.add_dependency(roles_stack)

    Tags.of(observability_stack).add("App", config.app_name_tag)
    Tags.of(observability_stack).add("Module", config.module_name_tag)
    Tags.of(observability_stack).add("Namespace", config.namespace)

    appinsights_stack = AppInsightsStack(
        app,
        f"{config.namespace}-AppInsightsStack",
        stack_name=f"{config.namespace}-AppInsightsStack",
        logger=logger,
        config=config,
        appinsightsstack={
            "stack_id": observability_stack.stack_id,
            "stack_name": observability_stack.stack_name,
            "component_name": observability_stack.alpha_instance.attr_instance_id,
        },
    )
    appinsights_stack.add_dependency(observability_stack)

    Tags.of(appinsights_stack).add("App", config.app_name_tag)
    Tags.of(appinsights_stack).add("Module", config.module_name_tag)
    Tags.of(appinsights_stack).add("Namespace", config.namespace)

    # vectordb_stack = VectorDBStack(
    #     app,
    #     f"{config.namespace}-VectorDBStack",
    #     stack_name=f"{config.namespace}-VectorDBStack",
    #     logger=logger,
    #     config=config,
    # )
    # vectordb_stack.add_dependency(ingestion_stack)

    # Tags.of(vectordb_stack).add("Name", config.app_name_tag)
    # Tags.of(vectordb_stack).add("Module", config.module_name_tag)
    # Tags.of(vectordb_stack).add("Namespace", config.namespace)

    # agents_stack = AgentsStack(
    #     app,
    #     f"{config.namespace}-AgentsStack",
    #     stack_name=f"{config.namespace}-AgentsStack",
    #     logger=logger,
    #     config=config,
    # )
    # agents_stack.add_dependency(vectordb_stack)

    # Tags.of(agents_stack).add("Name", config.app_name_tag)
    # Tags.of(agents_stack).add("Module", config.module_name_tag)
    # Tags.of(agents_stack).add("Namespace", config.namespace)

    # streamlit_stack = StreamlitStack(
    #     app,
    #     f"{config.namespace}-StreamlitStack",
    #     stack_name=f"{config.namespace}-StreamlitStack",
    #     logger=logger,
    #     config=config,
    # )
    # streamlit_stack.add_dependency(agents_stack)

    # Tags.of(streamlit_stack).add("Name", config.app_name_tag)
    # Tags.of(streamlit_stack).add("Module", config.module_name_tag)
    # Tags.of(streamlit_stack).add("Namespace", config.namespace)

    # Synthesize it
    logger.info("Synthesizing stack")
    app.synth()


if __name__ == "__main__":
    main()
