FROM amancevice/pandas:1.1.4-alpine

WORKDIR /anomaly_detector

ENV FLASK_APP main.py
ENV FLASK_RUN_HOST 0.0.0.0

#Install necessary packages for running Flask
RUN apk add --no-cache gcc musl-dev linux-headers

COPY . .

RUN pip install -r requirements.txt

ENTRYPOINT ["python", "main.py"]