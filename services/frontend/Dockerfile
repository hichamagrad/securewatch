FROM nginx:alpine

# Copie des fichiers statiques
COPY index.html /usr/share/nginx/html/index.html
COPY style.css /usr/share/nginx/html/style.css
COPY app.js /usr/share/nginx/html/app.js
COPY world-110m.json /usr/share/nginx/html/world-110m.json
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
