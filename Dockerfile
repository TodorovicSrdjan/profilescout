
FROM --platform=linux/amd64 python:3.9-buster

RUN mkdir /data

VOLUME /data

WORKDIR /app

RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'

RUN apt-get -y update \
    && apt-get install -y vim \
    && apt-get install -y google-chrome-stable \
    && apt-get install -yqq unzip

RUN wget -O /tmp/chromedriver.zip http://chromedriver.storage.googleapis.com/`curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE`/chromedriver_linux64.zip \
    && unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/

# set display port to avoid crash

ENV DISPLAY=:99

# install selenium

RUN pip install selenium==4.3.0 tldextract

COPY . .

CMD ["bash"]
