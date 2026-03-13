FROM docker.elastic.co/logstash/logstash:8.11.0

USER root

# Copy pipeline configuration
# Note: Build context is repo root, so paths are relative to that
COPY docker/config/logstash/logstash.conf /usr/share/logstash/pipeline/logstash.conf

# Copy logstash settings
COPY docker/config/logstash/logstash.yml /usr/share/logstash/config/logstash.yml

# Allow the entrypoint (running as non-root on platforms like Northflank) to edit config
RUN chown -R logstash:logstash /usr/share/logstash/config /usr/share/logstash/pipeline \
 && chmod -R g+rwX /usr/share/logstash/config /usr/share/logstash/pipeline

USER logstash
