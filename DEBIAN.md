# Installation notes for installation of Find3 on Debian 13

\#TODO - Add system user and login user.

Precondition: Debian system is installed, root user & default user, ssh enabled.

## Create users & access rights for the system

The system will be installed with a root user and a default user account. Login to the console as root and ensure the default user can issue commands as root.

```bash
apt update && apt -y upgrade && apt install sudo
sudo adduser <default> sudo
```

Login as the <default> user (preferably through ssh) and create a service account for the find3 server.

```bash
useradd -r find3
```

Add the default user to the find3 group, in order to be able to create, build and run the files during setup

```bash
sudo usermod -a -G find3 <default>
```

## Install pre-requisites for building the find3 server & setup environment

```bash
sudo apt -y install python3 python3-full golang-go g++ git mosquitto pip curl
```

## Clone the Find3 repository

```bash
sudo mkdir -p /opt/find3
sudo chown find3:find3 /opt/find3
sudo chmod 775 /opt/find3

sudo -u find3 git clone https://github.com/JarnoBoks/find3.git /opt/find3
git config --global --add safe.directory /opt/find3
```

## Setup environment variables for your build

* Setup the domain suffix of your server, fe. example.internal. After installation the find3 services will be listening to `https://find3.example.internal` and `https://find3server.example.internal`.
* Setup the email adres that will be used for the SSL certificate registration at LetsEncrypt.

  \

```bash
export FIND3DOMAINSFX=example.internal
export FIND3EMAIL=postmaster@example.internal
sudo /opt/find3/conf/setup_env.sh
```

## Build both servers (find3ai & find3server)


:::info
The sources for the find3ai server has changed from the upstream repository. The schollz/find3 repository is quit old and wouldn’t compile on Debian13. Versions for python modules in `find3/server/ai/requirements.txt` are updated to more recent ones.

:::

On debian the python environment is externally managed. We have to create a special environment for the find3 python application

```javascript
sudo mkdir -p /opt/python-find3
sudo chown find3:find3 /opt/python-find3/
sudo chmod 775 /opt/python-find3/
python3 -m venv /opt/python-find3
```

Install & build Python dependencies for find3ai.

```bash
cd /opt/find3/server/ai
/opt/python-find3/bin/python -m pip install -r requirements.txt
```

Build and install the find3server.

```bash
cd /opt/find3/server/main
go mod download github.com/NYTimes/gziphandler
go get github.com/schollz/find3/server/main/src/api
go get github.com/schollz/find3/server/main/src/database
go get github.com/schollz/find3/server/main/src/mqtt
go get github.com/schollz/find3/server/main/src/server
go build -v

sudo ln -s /opt/find3/server/main/main /usr/sbin/find3server
```

## Setup SSL reverse proxy for the find3server

Install nginx as remote proxy server

```bash
sudo apt install -y nginx
```

Request/create an SSL certificate for the find3server using the ACME.sh script, using Cloudflare dns

```bash
# Run these commands as root user
sudo -i

# Replace the data with your own credentials
export CF_Token=<your CF Token>
export CF_Account_ID=<your CF Account ID>

# Request the certificate
chmod +x /opt/find3/conf/setup-sslcert.sh
/opt/find3/conf/setup-sslcert.sh
rm /opt/find3/conf/setup-sslcert.sh
rm /opt/find3/conf/setup-sslcert

# Logout of the root-shell
exit
```

Setup the configuration for find3server within nginx

```bash
sudo cp /opt/find3/conf/nginx-find3.conf /etc/nginx/sites-available/find3.conf
sudo ln -s /etc/nginx/sites-available/find3.conf /etc/nginx/sites-enabled/find3.conf
sudo rm /etc/nginx/sites-enabled/default
```

## Create the systemd services to start the find3server at boot

Copy the configuration sample files, configuration and setup necessary folders.

```bash
# copy services
sudo cp /opt/find3/conf/find*.service /etc/systemd/system

# copy sample configuration
sudo cp /opt/find3/conf/find3server.default.sample /etc/default/find3

# create mqtt configuration folder expected by find3server.service
sudo mkdir -p /var/opt/find3server
sudo chown find3:find3 /var/opt/find3server
```

**Important:** change the sample configuration to your specific situation

```bash
sudo nano /etc/default/find3
```

## Enable the services and start find3

```bash
# Ensure the acl's are set correctly
sudo chown -R find3:find3 /opt/find3

# Start the services
sudo systemctl daemon-reload
sudo systemctl enable --now /etc/systemd/system/find3ai.service
sudo systemctl enable --now /etc/systemd/system/find3server.service
sudo systemctl reload nginx
```

If everything went well, the find3server will be available on the url that you specified, like [https://find3server.example.org]()

## Other information

* Before you can login to the frontend, the family has to be created. The easiest way to do such a thing is by learning a location. Check the Tasker scripts in this repository for more information
* The find3ai service will listen on the default port (8002)
* The find3server service will listen on port 8005. You can change this in `/etc/nginx/sites-available/find3.conf`
* To find out what cli parameters the find3server accepts, run `/usr/sbin/find3server -help`

## Todo

- [ ] Remove credentials from this file
- [ ] Set correct timezone for the server


