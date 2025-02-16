#!/bin/bash
echo "################ Custom Init Script: Started ################"
yum update -y

# Install Tomcat
amazon-linux-extras enable tomcat9
yum install -y tomcat tomcat-admin-webapps tomcat-webapps jq
systemctl start tomcat
systemctl enable tomcat
systemctl status tomcat --no-pager


# Install Nginx
amazon-linux-extras enable nginx1
yum install -y nginx
systemctl start nginx
systemctl enable nginx
systemctl status nginx --no-pager

# Install Cloudwatch Agent
yum install -y amazon-cloudwatch-agent

echo '
{{ cloudwatch_agent_config }}
' > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json

systemctl start amazon-cloudwatch-agent
systemctl enable amazon-cloudwatch-agent
systemctl status amazon-cloudwatch-agent --no-pager

# Install X-Ray Daemon
# curl https://s3.us-east-2.amazonaws.com/aws-xray-assets.us-east-2/xray-daemon/aws-xray-daemon-3.x.rpm -o /home/ec2-user/xray.rpm
# yum install -y /home/ec2-user/xray.rpm
# systemctl enable xray.service
# systemctl start xray.service
# systemctl status xray.service --no-pager

# Install Python 3.8
yum install -y python3-pip python3-dev python3-venv 
yum remove python3 
amazon-linux-extras install python3.8
rpm -ql python38
ln -sf /usr/bin/python3.8 /usr/bin/python3
ln -sf /usr/bin/pydoc3.8 /usr/bin/pydoc
python3 --version

# Run ADOT Collector
cd ~
wget -nv https://aws-otel-collector.s3.amazonaws.com/amazon_linux/amd64/latest/aws-otel-collector.rpm
rpm -Uvh  ./aws-otel-collector.rpm
/opt/aws/aws-otel-collector/bin/aws-otel-collector-ctl -a start
systemctl status aws-otel-collector 


# Install MySQL
amazon-linux-extras install epel -y
yum install -y https://dev.mysql.com/get/mysql80-community-release-el7-5.noarch.rpm
rpm --import https://repo.mysql.com/RPM-GPG-KEY-mysql-2023
yum install -y mysql-community-server 
systemctl enable mysqld 
systemctl start mysqld 
systemctl status mysqld --no-pager
temp_password=$(sudo grep 'temporary password' /var/log/mysqld.log | awk '{print $NF}')
new_password=A+a8th+++ms
mysql --connect-expired-password -u root -p$temp_password  -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$new_password';"
mysql -u root -p$new_password -e "CREATE DATABASE test;"
mysql -u root -p$new_password -e "SHOW DATABASES;"


# Download App
cd ~
APPS={{ nginx_apps }}
NAMESPACE={{ namespace }}
REGION={{ region }}

# Update the default page
cat <<EOF > /usr/share/nginx/html/index.html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Applications</title>
</head>
<body>
    <h1>Links</h1>
EOF
for app in "${APPS[@]}"; do
    echo "<a id=\"$app\" href=\"/$app\">$app</a><br>" >> /usr/share/nginx/html/index.html
done
cat <<EOF >> /usr/share/nginx/html/index.html
</body>
</html>
EOF

cat <<EOF > /etc/nginx/conf.d/$NAMESPACE.conf
server {
    listen 80;
    server_name $NAMESPACE.com;  
}
EOF

# Download all apps
aws s3 cp --recursive s3://{{ build_bucket }}/ .

export MYSQL_PASSWORD=$new_password

for script in "${APPS[@]}"; do  
    echo "################ Deploying ($script) ################"
    cd $script
    unzip *.zip
    # Add logs to CW
    sed -i "s/#namespace#/$NAMESPACE/g" logging.json    
    jq -s '.[0].logs.logs_collected.files.collect_list += .[1].logs.logs_collected.files.collect_list | .[0]' /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json logging.json > temp.json && mv temp.json /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json

    # Deploy app
    bash +x deploy.sh $NAMESPACE $REGION

    # Replace the last line with each apps nginx conf
    echo "$(head -n -1 /etc/nginx/conf.d/$NAMESPACE.conf)
    $(cat nginx.conf)"$'\n}' > /etc/nginx/conf.d/$NAMESPACE.conf
    cd ..
done

systemctl restart amazon-cloudwatch-agent
systemctl restart nginx

echo "################ Custom Init Script: Complete ################"