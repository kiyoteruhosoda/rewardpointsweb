FROM mariadb:10.11

# The schema and master data are not baked in; they are built by
# `alembic upgrade head` (entrypoint.sh) when the web container starts. This DB image is
# plain MariaDB with the time zone fixed to UTC.

ENV TZ=UTC

# Keep MariaDB's internal clock in UTC
CMD ["mysqld", "--default-time-zone=+00:00"]
