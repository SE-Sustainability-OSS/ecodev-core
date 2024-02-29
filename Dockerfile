###########
# BUILDER #
###########
FROM python:3.11-slim as builder

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install psycopg2 dependencies
RUN apt-get update && apt-get install -y postgresql-server-dev-all gcc python3-dev musl-dev

# install packages
RUN python3 -m pip install --upgrade pip
COPY ./requirements.txt /requirements.txt
RUN python3 -m pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt


#########
# FINAL #
#########
FROM python:3.11-slim

# Install dependencies
RUN apt-get update && apt-get install -y libpq-dev postgresql-client

COPY --from=builder /app/wheels /wheels
RUN python3 -m pip install --no-cache /wheels/*

## Ship code
COPY ecodev_core/ /app/ecodev_core
WORKDIR /app

#Opened ports
#Dash or Uvicorn
EXPOSE 80

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "80"]
