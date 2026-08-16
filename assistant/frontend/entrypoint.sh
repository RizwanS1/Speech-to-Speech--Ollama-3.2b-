#!/bin/sh
# entrypoint: write runtime config and start nginx
: ${FRONTEND_API_URL:=}
# write config.js that the browser can read
cat > /usr/share/nginx/html/config.js <<EOF
window.FRONTEND_API_URL = "${FRONTEND_API_URL}";
EOF

# Start nginx in foreground
exec nginx -g 'daemon off;'
