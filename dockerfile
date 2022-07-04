FROM python:3.10-slim
RUN pip3 install --upgrade pip
RUN pip3 install pymongo
RUN pip3 install python-telegram-bot==20.0a2 -U --pre