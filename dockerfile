FROM youseq/servicebaseimage:latest

COPY ./app /app

RUN pip install pymongo

ENV PYTHONUNBUFFERED=1

ENV PYTHONIOENCODING=UTF-8
