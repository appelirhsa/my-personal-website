# Portfolio + admin portal (FastAPI, GitHub, AWS Ubuntu)

```
server/main.py        FastAPI app: public site, admin API, GitHub commits, analytics
server/hash_password.py   makes the admin password hash
templates/            Jinja2 pages: home, works, one project, about, contact, 404 (server-rendered for Google and link previews)
admin/index.html      admin portal at /admin (metrics, profile, experience, education, skills, projects, media)
public/assets/        site.css and site.js
public/uploads/       images/ and files/ written by the admin portal (CV PDF lives in files/)
public/secure_pulse.html, dashboard.html   your original SecurePulse pages, unchanged
content/site-data.json   all editable site content
data/analytics.db     visit metrics (created at runtime, git-ignored)
```

## 1. Put it in your existing repo
Do this on a **branch** (for example `new-site`), not `main`, until the cutover: if the repo is published with GitHub Pages,
pushing to `main` would replace your live site. Copy these folders into the repo, keep the old files in `old-site/`,
commit and push the branch. Merge to `main` only when the new site is live on the server.
Pages note: the old `CNAME` file belongs to GitHub Pages; delete it after the DNS switch.

## 2. GitHub token
GitHub > Settings > Developer settings > Fine-grained tokens. Select **only** the website repo,
permission **Contents: Read and write**. Copy the token.

## 3. Server setup (Ubuntu)
```bash
sudo apt update && sudo apt install -y python3-venv nginx git
sudo git clone https://github.com/<owner>/<repo>.git /var/www/portfolio
sudo chown -R ubuntu:ubuntu /var/www/portfolio          # use your server user
cd /var/www/portfolio
python3 -m venv .venv && .venv/bin/pip install -r server/requirements.txt
cp server/.env.example server/.env && chmod 600 server/.env
.venv/bin/python server/hash_password.py                 # paste the printed line into server/.env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # paste as JWT_SECRET
nano server/.env                                         # also fill GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO
```

## 4. Run as a service
`/etc/systemd/system/portfolio.service`
```ini
[Unit]
Description=Portfolio (FastAPI)
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/var/www/portfolio
EnvironmentFile=/var/www/portfolio/server/.env
ExecStart=/var/www/portfolio/.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8001 --workers 1
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload && sudo systemctl enable --now portfolio
curl -s http://127.0.0.1:8001/api/site | head -c 200
```
Port 8001 is used so it cannot clash with the fire-detection dashboard; change it if that is taken.

## 5. Nginx + HTTPS
`/etc/nginx/sites-available/portfolio`
```nginx
server {
    listen 80;
    server_name appelirhsa.co.za www.appelirhsa.co.za;
    client_max_body_size 25m;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/portfolio /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d appelirhsa.co.za -d www.appelirhsa.co.za
```
Do not delete other `sites-enabled` files: the fire dashboard may depend on them.
Point the domain's A record at the instance's Elastic IP and open ports 80 and 443 in the security group.

## 6. Using it
Open `https://appelirhsa.co.za/admin`, sign in, edit, press **Save & publish**.
Each save is one commit to GitHub (`cms: update site content`) and the live site updates immediately.

## Keeping GitHub and the server in sync
Admin saves commit to GitHub and are mirrored on the server's disk, so the server clone drifts behind `main`.
When you push code changes from your laptop, update the server with:
```bash
cd /var/www/portfolio && git fetch origin && git reset --hard origin/main && sudo systemctl restart portfolio
```
`reset --hard` is safe here because every admin change is already committed to GitHub.
Only `server/.env`, `data/` and `.venv/` are untracked and survive it.

## Local test (no GitHub)
```bash
JWT_SECRET=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))") COOKIE_SECURE=0 \
ADMIN_PASSWORD_HASH=<hash> .venv/bin/uvicorn server.main:app --port 8001
```
With no `GITHUB_TOKEN` set, saves are written to local files only.

## Fonts and third-party requests
Geist, Inter, Font Awesome (solid) and Chart.js are all in `public/assets/` and are served by your own server after `git pull`.
Nothing is fetched from Google, Cloudflare or jsDelivr, and the site sets no cookies for visitors.
The only outside host a page can contact is Formspree (the contact form), which the Privacy Policy discloses.
(For the CV, the LaTeX build will use TeX Live fonts installed on the server.)

## Legal checklist (South Africa, POPIA)
Pages: `/privacy` (Privacy Policy) and `/terms` (Terms of Use & Legal Notice); both are linked in the footer.
Their wording lives in `templates/privacy.html` and `templates/terms.html`. If you change it, update `LEGAL_UPDATED` in `server/main.py`.
Things the policy promises that you must actually do:
1. **Contact messages:** delete them (in your email and in your Formspree account) within 12 months.
2. **Server logs:** keep Nginx's default rotation (`/etc/logrotate.d/nginx`, `rotate 14`); do not extend it.
3. **Statistics:** the app deletes rows older than 13 months by itself.
4. **Hosting region:** fill in the "Hosting region" field in Admin > Profile > Search & sharing.
5. **Photos and images:** only publish images you own or are licensed to use, and credit sources where required.
6. **CV:** it is a public download. Do not list other people's phone numbers or emails in it without their permission.
This is a good-faith template, not legal advice: have it reviewed by a lawyer or your institution's legal office, and check the
Information Regulator's guidance (inforegulator.org.za) on whether you must register an information officer.
