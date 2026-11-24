# SwiftSend 2.0 upgrade notes

This package is an incremental upgrade of the supplied SwiftSend project. Existing app names, URLs, templates, database and migration history are retained.

## Included improvements
- Added a permanent optional primary-driver relationship to fleet vehicles (migration `deliveries.0004`).
- Added validation to prevent allocating a driver or vehicle already committed to another active delivery.
- Tightened delivery mutation access to Operations staff and Dispatchers; Customer Support retains operational viewing access.
- Added a self-service profile page for name, email and phone number.
- Notification inbox no longer marks all notifications read merely by opening it.
- Notification click-through only redirects to a same-host safe URL.
- Corrected duplicate address columns in delivery CSV export.
- Added a SwiftSend SVG favicon.
- Corrected the definition of active deliveries so failed jobs are terminal.

## Important
This is an upgraded development baseline, not a production certification. Before live use, configure a production secret, PostgreSQL, HTTPS, private media storage, email provider, backups, monitoring, rate limiting and a reviewed POPIA/privacy policy. Run the full test suite and perform role-based acceptance testing before deployment.

## Upgrade
Back up your current database. Extract this project to a new folder. Create and activate a Python 3.11 virtual environment, install `requirements.txt`, then run `python manage.py migrate`, `python manage.py check`, `python manage.py makemigrations --check --dry-run`, and `python manage.py test`. Do not overwrite your original project folder.
