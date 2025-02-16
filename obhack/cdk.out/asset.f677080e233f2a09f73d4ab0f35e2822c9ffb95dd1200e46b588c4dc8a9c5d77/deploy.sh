app_name="nexusapp"
echo "Namespace: $1"
echo "Region: $2"
echo "AppName: $app_name"

python3 -m venv ${app_name}env
source ${app_name}env/bin/activate
pip3 install wheel gunicorn flask flask_cors aws-xray-sdk boto3 aws-opentelemetry-distro

aws ssm get-parameter --name /$1/$app_name --region $2 --with-decryption --query 'Parameter.Value' --output text > .env

gunicorn --log-level debug --error-logfile gunicorn_error.log --bind 0.0.0.0:5000 wsgi:app --daemon

deactivate


