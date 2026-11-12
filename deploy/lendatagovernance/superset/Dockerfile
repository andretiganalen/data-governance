# Apache Superset 6 + driver Trino, untuk menu Visualisasi di dalam Len Data Governance (:8585/visualisasi/).
# Superset ≥ 6.0 diperlukan karena mendukung subpath (SUPERSET_APP_ROOT); tidak ada port terpisah yang dibuka.
FROM apache/superset:6.0.0
USER root
RUN uv pip install --no-cache --python /app/.venv/bin/python "trino[sqlalchemy]==0.340.0" "psycopg2-binary==2.9.10"
COPY superset_config.py /app/pythonpath/superset_config.py
COPY dg_sso.py /app/pythonpath/dg_sso.py
COPY entrypoint.sh /app/docker/dg-entrypoint.sh
COPY len-logo.png /app/superset/static/assets/images/len-logo.png
# Bahasa Indonesia (Superset tidak menyediakannya): dibangun dari translations/id.json + messages.pot bawaan image
COPY translations/id.json /tmp/id.json
COPY translations/build_id.py /tmp/build_id.py
RUN /app/.venv/bin/python /tmp/build_id.py /app/superset/translations /tmp/id.json && rm -f /tmp/build_id.py /tmp/id.json
RUN chmod 755 /app/docker/dg-entrypoint.sh
ENV SUPERSET_APP_ROOT=/visualisasi
USER superset
ENTRYPOINT ["/app/docker/dg-entrypoint.sh"]
