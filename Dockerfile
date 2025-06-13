#INSTALLED debain-bullseys image
FROM debian:bullseye

WORKDIR /app

# Copy files
COPY . /app


# Install system dependencies like python3 and pip,nan0
RUN apt-get update && \
    apt-get install -y \
    python3 \
    python3-pip \
    sqlite3 \
    nano \
    libgpiod2 \
    procps \
    curl \
    iputils-ping && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* 

 RUN pip3 install minimalmodbus PyYAML python-dotenv requests RPi.GPIO Adafruit_DHT psutil board netifaces

    

#RUN pip3 install --no-cache-dir -r requirements.txt
ENTRYPOINT [ "python3", "main.py" ]
#CMD [ "python3", "main.py" ]
#ENTRYPOINT ["sh", "-c", "python3 main.py && tail -f /dev/null"]
