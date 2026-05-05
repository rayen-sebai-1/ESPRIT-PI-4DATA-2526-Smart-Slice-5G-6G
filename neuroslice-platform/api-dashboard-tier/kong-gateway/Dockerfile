FROM kong:3.7

# No extra packages needed — docker-entrypoint.sh uses only sed and sh,
# both of which are present in the base image.

# Copy the config template (not the final config — that is generated at runtime
# by docker-entrypoint.sh so secrets never have to be baked into the image).
COPY api-dashboard-tier/kong-gateway/kong.yml /etc/kong/kong.yml.template

# --chmod sets the execute bit at copy time; avoids a separate RUN chmod layer.
COPY --chmod=755 api-dashboard-tier/kong-gateway/docker-entrypoint.sh /neuroslice-entrypoint.sh

ENTRYPOINT ["/neuroslice-entrypoint.sh"]
CMD ["kong", "docker-start"]
