FROM surnet/alpine-python-wkhtmltopdf:3.7.3-0.12.5-small
WORKDIR app
RUN mkdir out_data

RUN apk add build-base # gcc
RUN apk add libffi libffi-dev
RUN apk --no-cache --update --upgrade add gcc musl-dev jpeg-dev zlib-dev libffi-dev cairo-dev pango-dev gdk-pixbuf-dev
RUN apk add -U tzdata
ENV TZ=Europe/Moscow
RUN pip install tzdata tzlocal pytz
RUN ln -fs /usr/share/zoneinfo/Etc/GMT+3 /etc/localtime
RUN rm -rf /var/cache/apk/*

COPY requirements.txt /app/
RUN pip install -r requirements.txt
COPY *.py  /app/
CMD ["python", "handlers.py"]
