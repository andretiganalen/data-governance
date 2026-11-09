# Apache Superset + driver Trino, untuk dashboard di atas lakekeeper.medallion_repository (Gold).
FROM apache/superset:4.1.2
USER root
RUN pip install --no-cache-dir "trino[sqlalchemy]==0.340.0" "psycopg2-binary==2.9.10"
COPY superset_config.py /app/pythonpath/superset_config.py
COPY entrypoint.sh /app/docker/dg-entrypoint.sh
COPY len-logo.png /app/superset/static/assets/images/len-logo.png
RUN chmod 755 /app/docker/dg-entrypoint.sh
USER superset
ENTRYPOINT ["/app/docker/dg-entrypoint.sh"]
