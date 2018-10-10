FROM python:3.6.1

# prepare env
ENV APP_DIR /app
WORKDIR ${APP_DIR}
ADD . ${APP_DIR}/

# Install all in one.
RUN groupadd appgroup && useradd -m -g appgroup -s /bin/bash appuser \
 && pip install --no-cache-dir gunicorn gevent \
 && pip install --no-cache-dir -r ${APP_DIR}/requirements.txt \
 && chown -R appuser:appgroup ${APP_DIR}

USER appuser
ENTRYPOINT ["/usr/local/bin/gunicorn", "-k", "gevent", "-b", ":8000", "argg_api.main:app"]
