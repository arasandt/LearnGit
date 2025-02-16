echo "Namespace: $1"
echo "Region: $2"

python3 -m venv nexusappenv
source nexusappenv/bin/activate
pip3 install wheel gunicorn flask flask_cors aws-xray-sdk boto3 aws-opentelemetry-distro

aws ssm get-parameter --name /$1/nexusapp --region $2 --with-decryption --query 'Parameter.Value' --output text > .env

gunicorn --log-level debug --error-logfile gunicorn_error.log --bind 0.0.0.0:5000 wsgi:app --daemon
deactivate

/bin/cp -f nexusapp.conf /etc/nginx/conf.d/nexusapp.conf


