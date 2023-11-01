FROM python:3.11
WORKDIR /usr/src/app

RUN pip install coveralls
ADD requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python ./setup.py test
CMD ["python", "./setup.py", "test"]
