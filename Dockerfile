#INSTALLED debain-bullseys image
FROM debian:bullseye-20250520-slim

WORKDIR /app

# Copy files
COPY . /app

# Install system dependencies like python3 and pip,nan0

RUN apt-get update && \
    apt-get install -y \
    python3=3.9.2-3 python3-pip=20.3.4-4+deb11u1 sqlite3=3.34.1-3+deb11u1 nano libgpiod2=1.6.2-1 procps=2:3.3.17-5 curl=7.74.0-1.3+deb11u14 iputils-ping=3:20210202-1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip3 install --no-cache-dir -r requirements.txt

#RUN pip3 install --no-cache-dir -r requirements.txt
ENTRYPOINT [ "python3", "main.py" ]
#CMD [ "python3", "main.py" ]
#ENTRYPOINT ["sh", "-c", "python3 main.py && tail -f /dev/null"]
