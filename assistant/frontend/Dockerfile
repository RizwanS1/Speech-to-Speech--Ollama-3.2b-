FROM nginx:stable-alpine

# Copy nginx config (paths are relative to the build context which is the repo root)
COPY assistant/frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy the repository static site into nginx html directory
COPY assistant/server/static /usr/share/nginx/html

# Entrypoint will generate config.js from env and start nginx
COPY assistant/frontend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
