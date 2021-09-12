FROM python

RUN pip install todus3 todus3[7z]
WORKDIR /todus3
VOLUME [ "/todus3" ]
ENTRYPOINT [ "todus3" ]