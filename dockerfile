FROM youseq/servicebaseimage:v1.0.0

COPY ./app /app

RUN pip install pymongo

ENV PYTHONUNBUFFERED=1

ENV PYTHONIOENCODING=UTF-8
