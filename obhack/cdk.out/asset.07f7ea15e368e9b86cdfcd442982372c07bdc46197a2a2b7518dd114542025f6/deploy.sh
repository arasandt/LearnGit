echo "Namespace: $1"
echo "Region: $2"

python3 -m venv nobleappenv
source nobleappenv/bin/activate
pip3 install wheel gunicorn flask flask_cors aws-xray-sdk boto3 aws-opentelemetry-distro

aws ssm get-parameter --name /$1/nobleapp --region $2 --with-decryption --query 'Parameter.Value' --output text > .env

export OTEL_METRICS_EXPORTER=none
export OTEL_LOGS_EXPORTER=none
# export OTEL_TRACES_EXPORTER=oltp
export OTEL_AWS_APPLICATION_SIGNALS_ENABLED=true
export OTEL_PYTHON_DISTRO=aws_distro
export OTEL_PYTHON_CONFIGURATOR=aws_configurator
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_TRACES_SAMPLER=xray
export TEL_TRACES_SAMPLER_ARG="endpoint=http://localhost:2000,polling_interval=60" 
export OTEL_AWS_APPLICATION_SIGNALS_EXPORTER_ENDPOINT=http://localhost:4316/v1/metrics
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4316/v1/traces
export OTEL_RESOURCE_ATTRIBUTES="service.name=nobleapp,cloud.provider=aws,cloud.platform=ec2"
# export OTEL_EXPORTER_OTLP_ENDPOINT=http://<your-collector-ip>:4317
opentelemetry-instrument gunicorn --log-level debug --error-logfile gunicorn_error.log --bind 0.0.0.0:5001 wsgi:app --daemon

deactivate

/bin/cp -f nobleapp.conf /etc/nginx/conf.d/nobleapp.conf


