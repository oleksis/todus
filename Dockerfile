FROM python:3.9.6-slim
# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE 1
# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED 1

# Install and setup poetry
RUN pip install -U pip \
    && apt-get update \
    && apt install -y curl netcat \
    && curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -
ENV PATH="${PATH}:/root/.poetry/bin"

WORKDIR /var/app
COPY . .
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi \
  && chmod +x /var/app/entrypoint.sh

ENTRYPOINT ["/var/app/entrypoint.sh"]



#RUN pip install todus3[7z]
#WORKDIR /todus3
#VOLUME [ "/todus3" ]
#ENTRYPOINT [ "todus3" ]