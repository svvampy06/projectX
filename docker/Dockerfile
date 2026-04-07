FROM python:3.13.4-alpine3.22
WORKDIR /app
COPY *.py .
COPY requirements.txt .
RUN pip3 install -r requirements.txt
CMD ["uvicorn", "main:app", "--reload", "--host=0.0.0.0"]