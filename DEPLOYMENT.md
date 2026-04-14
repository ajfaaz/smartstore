# SmartStore Deployment Flow (GitHub -> cPanel)

## 1) One-time local setup

```bash
git init
git branch -M main
git add .
git commit -m "Initial smartstore setup"
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

## 2) One-time cPanel server setup

1. Enable SSH access in cPanel.
2. Clone this GitHub repo on the server into your Python app directory.
3. Confirm your Python app uses the same folder where `passenger_wsgi.py` exists.
4. Confirm virtualenv python path (example):
   `/home/<cpanel_user>/virtualenv/smartstore/3.11/bin/python`

## 3) GitHub repository secrets

Add these secrets in GitHub:

- `CPANEL_HOST`: `smartstore.arewanetventures.com`
- `CPANEL_USER`: your cPanel SSH username
- `CPANEL_SSH_KEY`: private SSH key (for the matching public key on cPanel)
- `CPANEL_PORT`: usually `22`
- `CPANEL_APP_PATH`: absolute project path on cPanel server
- `CPANEL_VENV_PYTHON`: absolute python path in cPanel virtualenv

## 4) Automatic deploy behavior

Any push to `main` runs:

1. `python manage.py check`
2. SSH deploy on cPanel:
   - `git pull`
   - `pip install -r requirements.txt`
   - `python manage.py migrate --noinput`
   - `python manage.py collectstatic --noinput`
   - `touch passenger_wsgi.py` (restart app)

## 5) Typical daily workflow

```bash
git add .
git commit -m "Describe change"
git push
```

That push triggers deployment automatically.
