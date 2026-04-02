FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ARG INSTALL_DEV=true

WORKDIR /app

COPY requirements ./requirements
RUN pip install --no-cache-dir -r requirements/prod.txt \
    && if [ "$INSTALL_DEV" = "true" ]; then pip install --no-cache-dir -r requirements/dev.txt; fi

COPY . .
RUN chmod +x /app/scripts/container-start.sh

RUN DJANGO_ENV=production DJANGO_SECRET_KEY=build-dummy-key DATABASE_URL=sqlite:///tmp/dummy.db \
    python manage.py collectstatic --noinput

EXPOSE 8000

ENTRYPOINT ["/app/scripts/container-start.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
